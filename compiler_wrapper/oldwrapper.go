package main

import (
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"text/template"
)

func calcOldCompilerCommands(env env, cfg *config, wrapperCmd *command) ([]*command, error) {
	stdoutBuffer := bytes.Buffer{}
	stderrBuffer := bytes.Buffer{}
	pipes := exec.Cmd{
		Stdin:  strings.NewReader(""),
		Stdout: &stdoutBuffer,
		Stderr: &stderrBuffer,
	}
	mockForks := true
	if err := callOldWrapper(env, cfg, wrapperCmd, &pipes, mockForks); err != nil {
		return nil, fmt.Errorf("error: %s. %s", err, stderrBuffer.String())
	}

	// Parse the nested commands.
	allStderrLines := strings.Split(stderrBuffer.String(), "\n")
	var commands []*command
	for _, line := range allStderrLines {
		const commandPrefix = "command:"
		const envupdatePrefix = ".EnvUpdate:"
		envUpdateIdx := strings.Index(line, ".EnvUpdate:")
		if strings.Index(line, commandPrefix) >= 0 {
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
			commands = append(commands, command)
		}
	}
	return commands, nil
}

func forwardToOldWrapper(env env, cfg *config, wrapperCmd *command) error {
	pipes := exec.Cmd{
		Stdin:  os.Stdin,
		Stdout: os.Stdout,
		Stderr: os.Stderr,
	}
	mockForks := false
	return callOldWrapper(env, cfg, wrapperCmd, &pipes, mockForks)
}

func callOldWrapper(env env, cfg *config, wrapperCmd *command, pipes *exec.Cmd, mockForks bool) error {
	mockFile, err := ioutil.TempFile("", "compiler_wrapper_mock")
	if err != nil {
		return err
	}
	defer os.Remove(mockFile.Name())

	if err := writeOldWrapperMock(mockFile, env, cfg, wrapperCmd, mockForks); err != nil {
		return err
	}
	if err := mockFile.Close(); err != nil {
		return err
	}

	// Call the wrapper.
	cmd := newExecCmd(env, wrapperCmd)
	ensurePathEnv(cmd)
	// Note: Using a self executable wrapper does not work due to a race condition
	// on unix systems. See https://github.com/golang/go/issues/22315
	cmd.Args = append([]string{"/usr/bin/python2", "-S", mockFile.Name()}, cmd.Args[1:]...)
	cmd.Path = cmd.Args[0]
	cmd.Stdin = pipes.Stdin
	cmd.Stdout = pipes.Stdout
	cmd.Stderr = pipes.Stderr
	return cmd.Run()
}

func writeOldWrapperMock(writer io.Writer, env env, cfg *config, wrapperCmd *command, mockForks bool) error {
	absOldWrapperPath := cfg.oldWrapperPath
	if !filepath.IsAbs(absOldWrapperPath) {
		absWrapperDir, err := getAbsWrapperDir(env, wrapperCmd.path)
		if err != nil {
			return err
		}
		absOldWrapperPath = filepath.Join(absWrapperDir, cfg.oldWrapperPath)
	}
	oldWrapperContentBytes, err := ioutil.ReadFile(absOldWrapperPath)
	if err != nil {
		return err
	}
	oldWrapperContent := string(oldWrapperContentBytes)
	// Disable the original call to main()
	oldWrapperContent = strings.ReplaceAll(oldWrapperContent, "__name__", "'none'")
	// Inject the value of cfg.useCCache
	if !cfg.useCCache {
		oldWrapperContent = regexp.MustCompile(`True\s+#\s+@CCACHE_DEFAULT@`).ReplaceAllString(oldWrapperContent, "False #")
	}

	// Note: Fieldnames need to be upper case so that they can be read via reflection.
	mockData := struct {
		CmdPath           string
		OldWrapperContent string
		RootRelPath       string
		MockForks         bool
		OverwriteConfig   bool
		CommonFlags       []string
		GccFlags          []string
		ClangFlags        []string
	}{
		wrapperCmd.path,
		oldWrapperContent,
		cfg.rootRelPath,
		mockForks,
		cfg.overrideOldWrapperConfig,
		cfg.commonFlags,
		cfg.gccFlags,
		cfg.clangFlags,
	}

	const mockTemplate = `{{.OldWrapperContent}}
{{if .MockForks}}
init_env = os.environ.copy()

def serialize_cmd(args):
	current_env = os.environ
	envupdate = [k + "=" + current_env.get(k, '') for k in set(list(current_env.keys()) + list(init_env.keys())) if current_env.get(k, '') != init_env.get(k, '')]
	print('command:%s.EnvUpdate:%s\n' % (' '.join(args), ' '.join(envupdate)), file=sys.stderr)

def execv_mock(binary, args):
	serialize_cmd([binary] + args[1:])
	sys.exit(0)

os.execv = execv_mock
{{end}}

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
		return err
	}

	return tmpl.Execute(writer, mockData)
}

func ensurePathEnv(cmd *exec.Cmd) {
	for _, env := range cmd.Env {
		if strings.HasPrefix(env, "PATH=") {
			return
		}
	}
	cmd.Env = append(cmd.Env, "PATH=")
}
