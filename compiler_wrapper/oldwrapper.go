package main

import (
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"text/template"
)

const forwardToOldWrapperFilePattern = "old_wrapper_forward"
const compareToOldWrapperFilePattern = "old_wrapper_compare"

// Whether the command should be executed by the old wrapper as we don't
// support it yet.
func shouldForwardToOldWrapper(env env, inputCmd *command) bool {
	for _, arg := range inputCmd.args {
		if arg == "-clang-syntax" {
			return true
		}
	}
	switch {
	case env.getenv("WITH_TIDY") != "":
		fallthrough
	case env.getenv("FORCE_DISABLE_WERROR") != "":
		fallthrough
	case env.getenv("GETRUSAGE") != "":
		fallthrough
	case env.getenv("BISECT_STAGE") != "":
		return true
	}
	return false
}

func forwardToOldWrapper(env env, cfg *config, inputCmd *command) (exitCode int, err error) {
	oldWrapperCfg, err := newOldWrapperConfig(env, cfg, inputCmd)
	if err != nil {
		return 0, err
	}
	return callOldWrapper(env, oldWrapperCfg, inputCmd, forwardToOldWrapperFilePattern, env.stdout(), env.stderr())
}

func compareToOldWrapper(env env, cfg *config, inputCmd *command, newCmdResults []*commandResult) error {
	oldWrapperCfg, err := newOldWrapperConfig(env, cfg, inputCmd)
	if err != nil {
		return err
	}
	oldWrapperCfg.LogCmds = true
	oldWrapperCfg.MockCmds = cfg.mockOldWrapperCmds
	for _, cmdResult := range newCmdResults {
		oldWrapperCfg.CmdResults = append(oldWrapperCfg.CmdResults, oldWrapperCmdResult{
			Stdout:   cmdResult.stdout,
			Stderr:   cmdResult.stderr,
			Exitcode: cmdResult.exitCode,
		})
	}
	oldWrapperCfg.OverwriteConfig = cfg.overwriteOldWrapperCfg

	stdoutBuffer := bytes.Buffer{}
	stderrBuffer := bytes.Buffer{}
	exitCode, err := callOldWrapper(env, oldWrapperCfg, inputCmd, compareToOldWrapperFilePattern, &stdoutBuffer, &stderrBuffer)
	if err != nil {
		return err
	}
	oldCmdResults := parseOldWrapperCommands(stdoutBuffer.String(), stderrBuffer.String(), exitCode)
	return diffCommandResults(oldCmdResults, newCmdResults)
}

func parseOldWrapperCommands(stdout string, stderr string, exitCode int) []*commandResult {
	allStderrLines := strings.Split(stderr, "\n")
	remainingStderrLines := []string{}
	cmdResults := []*commandResult{}
	for _, line := range allStderrLines {
		const commandPrefix = "command:"
		const envupdatePrefix = ".EnvUpdate:"
		envUpdateIdx := strings.Index(line, envupdatePrefix)
		if strings.Index(line, commandPrefix) == 0 {
			if envUpdateIdx == -1 {
				envUpdateIdx = len(line) - 1
			}
			args := strings.Fields(line[len(commandPrefix):envUpdateIdx])
			envUpdateStr := line[envUpdateIdx+len(envupdatePrefix):]
			envUpdate := strings.Fields(envUpdateStr)
			if len(envUpdate) == 0 {
				// normalize empty slice to nil to make comparing empty envUpdates
				// simpler.
				envUpdate = nil
			}
			command := &command{
				path:       args[0],
				args:       args[1:],
				envUpdates: envUpdate,
			}
			cmdResults = append(cmdResults, &commandResult{cmd: command})
		} else {
			remainingStderrLines = append(remainingStderrLines, line)
		}
	}
	remainingStderr := strings.TrimSpace(strings.Join(remainingStderrLines, "\n"))
	if len(cmdResults) > 0 {
		lastCmdResult := cmdResults[len(cmdResults)-1]
		lastCmdResult.exitCode = exitCode
		lastCmdResult.stderr = remainingStderr
		lastCmdResult.stdout = strings.TrimSpace(stdout)
	}

	return cmdResults
}

func diffCommandResults(oldCmdResults []*commandResult, newCmdResults []*commandResult) error {
	maxLen := len(newCmdResults)
	if maxLen < len(oldCmdResults) {
		maxLen = len(oldCmdResults)
	}
	hasDifferences := false
	var cmdDifferences []string
	for i := 0; i < maxLen; i++ {
		var differences []string
		if i >= len(newCmdResults) {
			differences = append(differences, "missing command")
		} else if i >= len(oldCmdResults) {
			differences = append(differences, "extra command")
		} else {
			newCmdResult := newCmdResults[i]
			oldCmdResult := oldCmdResults[i]

			if i == maxLen-1 && newCmdResult.exitCode != oldCmdResult.exitCode {
				// We do not capture errors in nested commands from the old wrapper,
				// so only compare the exit codes of the final compiler command.
				differences = append(differences, "exit code")
			}

			if newCmdResult.cmd.path != oldCmdResult.cmd.path {
				differences = append(differences, "path")
			}

			if !reflect.DeepEqual(newCmdResult.cmd.args, oldCmdResult.cmd.args) {
				differences = append(differences, "args")
			}

			// Sort the environment as we don't care in which order
			// it was modified.
			newEnvUpdates := newCmdResult.cmd.envUpdates
			sort.Strings(newEnvUpdates)
			oldEnvUpdates := oldCmdResult.cmd.envUpdates
			sort.Strings(oldEnvUpdates)

			if !reflect.DeepEqual(newEnvUpdates, oldEnvUpdates) {
				differences = append(differences, "env updates")
			}
		}
		if len(differences) > 0 {
			hasDifferences = true
		} else {
			differences = []string{"none"}
		}
		cmdDifferences = append(cmdDifferences,
			fmt.Sprintf("Index %d: %s", i, strings.Join(differences, ",")))
	}
	if hasDifferences {
		return newErrorwithSourceLocf("commands differ:\n%s\nOld commands:\n%s\nNew commands:\n%s",
			strings.Join(cmdDifferences, "\n"),
			dumpCommandResults(oldCmdResults),
			dumpCommandResults(newCmdResults),
		)
	}
	return nil
}

func dumpCommandResults(results []*commandResult) string {
	lines := []string{}
	for _, result := range results {
		lines = append(lines, fmt.Sprintf("cmd: %#v; result: %#v", result.cmd, result))
	}
	return strings.Join(lines, "\n")
}

// Note: field names are upper case so they can be used in
// a template via reflection.
type oldWrapperConfig struct {
	CmdPath           string
	OldWrapperContent string
	RootRelPath       string
	LogCmds           bool
	MockCmds          bool
	CmdResults        []oldWrapperCmdResult
	OverwriteConfig   bool
	CommonFlags       []string
	GccFlags          []string
	ClangFlags        []string
}

type oldWrapperCmdResult struct {
	Stdout   string
	Stderr   string
	Exitcode int
}

func newOldWrapperConfig(env env, cfg *config, inputCmd *command) (*oldWrapperConfig, error) {
	absOldWrapperPath := cfg.oldWrapperPath
	if !filepath.IsAbs(absOldWrapperPath) {
		absWrapperDir, err := getAbsWrapperDir(env, inputCmd.path)
		if err != nil {
			return nil, err
		}
		absOldWrapperPath = filepath.Join(absWrapperDir, cfg.oldWrapperPath)
	}
	oldWrapperContentBytes, err := ioutil.ReadFile(absOldWrapperPath)
	if err != nil {
		return nil, wrapErrorwithSourceLocf(err, "failed to read old wrapper")
	}
	oldWrapperContent := string(oldWrapperContentBytes)
	// Disable the original call to main()
	oldWrapperContent = strings.ReplaceAll(oldWrapperContent, "__name__", "'none'")
	// Inject the value of cfg.useCCache
	if !cfg.useCCache {
		oldWrapperContent = regexp.MustCompile(`True\s+#\s+@CCACHE_DEFAULT@`).ReplaceAllString(oldWrapperContent, "False #")
	}

	return &oldWrapperConfig{
		CmdPath:           inputCmd.path,
		OldWrapperContent: oldWrapperContent,
		RootRelPath:       cfg.rootRelPath,
		CommonFlags:       cfg.commonFlags,
		GccFlags:          cfg.gccFlags,
		ClangFlags:        cfg.clangFlags,
	}, nil
}

func callOldWrapper(env env, cfg *oldWrapperConfig, inputCmd *command, filepattern string, stdout io.Writer, stderr io.Writer) (exitCode int, err error) {
	mockFile, err := ioutil.TempFile("", filepattern)
	if err != nil {
		return 0, wrapErrorwithSourceLocf(err, "failed to create tempfile")
	}
	defer os.Remove(mockFile.Name())

	const mockTemplate = `{{.OldWrapperContent}}
import subprocess

init_env = os.environ.copy()

mockResults = [{{range .CmdResults}} {
	'stdout': '{{.Stdout}}',
	'stderr': '{{.Stderr}}',
	'exitcode': {{.Exitcode}},
},{{end}}]

def serialize_cmd(args):
	{{if .LogCmds}}
	current_env = os.environ
	envupdate = [k + "=" + current_env.get(k, '') for k in set(list(current_env.keys()) + list(init_env.keys())) if current_env.get(k, '') != init_env.get(k, '')]
	print('command:%s.EnvUpdate:%s' % (' '.join(args), ' '.join(envupdate)), file=sys.stderr)
	{{end}}

def check_output_mock(args):
	serialize_cmd(args)
	{{if .MockCmds}}
	result = mockResults.pop(0)
	print(result['stderr'], file=sys.stderr)
	if result['exitcode']:
		raise subprocess.CalledProcessError(result['exitcode'])
	return result['stdout']
	{{else}}
	return old_check_output(args)
	{{end}}

old_check_output = subprocess.check_output
subprocess.check_output = check_output_mock

def execv_mock(binary, args):
	serialize_cmd([binary] + args[1:])
	{{if .MockCmds}}
	result = mockResults.pop(0)
	print(result['stdout'], file=sys.stdout)
	print(result['stderr'], file=sys.stderr)
	sys.exit(result['exitcode'])
	{{else}}
	old_execv(binary, args)
	{{end}}

old_execv = os.execv
os.execv = execv_mock

sys.argv[0] = '{{.CmdPath}}'

ROOT_REL_PATH = '{{.RootRelPath}}'

{{if .OverwriteConfig}}
FLAGS_TO_ADD=set([{{range .CommonFlags}}'{{.}}',{{end}}])
GCC_FLAGS_TO_ADD=set([{{range .GccFlags}}'{{.}}',{{end}}])
CLANG_FLAGS_TO_ADD=set([{{range .ClangFlags}}'{{.}}',{{end}}])
{{end}}

sys.exit(main())
`
	tmpl, err := template.New("mock").Parse(mockTemplate)
	if err != nil {
		return 0, wrapErrorwithSourceLocf(err, "failed to parse old wrapper template")
	}
	if err := tmpl.Execute(mockFile, cfg); err != nil {
		return 0, wrapErrorwithSourceLocf(err, "failed execute old wrapper template")
	}
	if err := mockFile.Close(); err != nil {
		return 0, wrapErrorwithSourceLocf(err, "failed to close temp file")
	}
	buf := bytes.Buffer{}
	tmpl.Execute(&buf, cfg)

	// Note: Using a self executable wrapper does not work due to a race condition
	// on unix systems. See https://github.com/golang/go/issues/22315
	if err := env.run(&command{
		path:       "/usr/bin/python2",
		args:       append([]string{"-S", mockFile.Name()}, inputCmd.args...),
		envUpdates: inputCmd.envUpdates,
	}, stdout, stderr); err != nil {
		if exitCode, ok := getExitCode(err); ok {
			return exitCode, nil
		}
		return 0, wrapErrorwithSourceLocf(err, "failed to call old wrapper. Command: %s %s",
			inputCmd.path, inputCmd.args)
	}
	return 0, nil
}
