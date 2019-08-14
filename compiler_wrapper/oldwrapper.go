// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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

const compareToOldWrapperFilePattern = "old_wrapper_compare"

func compareToOldWrapper(env env, cfg *config, inputCmd *command, newCmdResults []*commandResult, newExitCode int) error {
	pythonStringEscaper := strings.NewReplacer("\n", "\\n", "'", "\\'")

	oldWrapperCfg, err := newOldWrapperConfig(env, cfg, inputCmd)
	if err != nil {
		return err
	}
	oldWrapperCfg.MockCmds = cfg.mockOldWrapperCmds
	newCmds := []*command{}
	for _, cmdResult := range newCmdResults {
		oldWrapperCfg.CmdResults = append(oldWrapperCfg.CmdResults, oldWrapperCmdResult{
			Stdout:   pythonStringEscaper.Replace(cmdResult.Stdout),
			Stderr:   pythonStringEscaper.Replace(cmdResult.Stderr),
			Exitcode: cmdResult.ExitCode,
		})
		newCmds = append(newCmds, cmdResult.Cmd)
	}

	stderrBuffer := bytes.Buffer{}
	oldExitCode := 0
	if strings.HasPrefix(oldWrapperCfg.OldWrapperContent, "#!/bin/sh") {
		oldExitCode, err = callOldShellWrapper(env, oldWrapperCfg, inputCmd, compareToOldWrapperFilePattern, &bytes.Buffer{}, &stderrBuffer)
	} else {
		oldExitCode, err = callOldPythonWrapper(env, oldWrapperCfg, inputCmd, compareToOldWrapperFilePattern, &bytes.Buffer{}, &stderrBuffer)
	}
	if err != nil {
		return err
	}
	differences := []string{}
	if oldExitCode != newExitCode {
		differences = append(differences, fmt.Sprintf("exit codes differ: old %d, new %d", oldExitCode, newExitCode))
	}
	oldCmds, stderr := parseOldWrapperCommands(stderrBuffer.String())
	if cmdDifferences := diffCommands(oldCmds, newCmds); cmdDifferences != "" {
		differences = append(differences, cmdDifferences)
	}
	if len(differences) > 0 {
		return newErrorwithSourceLocf("wrappers differ:\n%s\nOld stderr:%s",
			strings.Join(differences, "\n"),
			stderr,
		)
	}
	return nil
}

func parseOldWrapperCommands(stderr string) (cmds []*command, remainingStderr string) {
	allStderrLines := strings.Split(stderr, "\n")
	remainingStderrLines := []string{}
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
			cmd := &command{
				Path:       args[0],
				Args:       args[1:],
				EnvUpdates: envUpdate,
			}
			cmds = append(cmds, cmd)
		} else {
			remainingStderrLines = append(remainingStderrLines, line)
		}
	}
	remainingStderr = strings.TrimSpace(strings.Join(remainingStderrLines, "\n"))
	return cmds, remainingStderr
}

func diffCommands(oldCmds []*command, newCmds []*command) string {
	maxLen := len(newCmds)
	if maxLen < len(oldCmds) {
		maxLen = len(oldCmds)
	}
	hasDifferences := false
	var cmdDifferences []string
	for i := 0; i < maxLen; i++ {
		var differences []string
		if i >= len(newCmds) {
			differences = append(differences, "missing command")
		} else if i >= len(oldCmds) {
			differences = append(differences, "extra command")
		} else {
			newCmd := newCmds[i]
			oldCmd := oldCmds[i]

			if newCmd.Path != oldCmd.Path {
				differences = append(differences, "path")
			}

			if !reflect.DeepEqual(newCmd.Args, oldCmd.Args) {
				differences = append(differences, "args")
			}

			// Sort the environment as we don't care in which order
			// it was modified.
			copyAndSort := func(data []string) []string {
				result := make([]string, len(data))
				copy(result, data)
				sort.Strings(result)
				return result
			}

			newEnvUpdates := copyAndSort(newCmd.EnvUpdates)
			oldEnvUpdates := copyAndSort(oldCmd.EnvUpdates)

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
		return fmt.Sprintf("commands differ:\n%s\nOld:%#v\nNew:%#v",
			strings.Join(cmdDifferences, "\n"),
			dumpCommands(oldCmds),
			dumpCommands(newCmds))
	}
	return ""
}

func dumpCommands(cmds []*command) string {
	lines := []string{}
	for _, cmd := range cmds {
		lines = append(lines, fmt.Sprintf("%#v", cmd))
	}
	return strings.Join(lines, "\n")
}

// Note: field names are upper case so they can be used in
// a template via reflection.
type oldWrapperConfig struct {
	WrapperPath       string
	CmdPath           string
	OldWrapperContent string
	MockCmds          bool
	CmdResults        []oldWrapperCmdResult
}

type oldWrapperCmdResult struct {
	Stdout   string
	Stderr   string
	Exitcode int
}

func newOldWrapperConfig(env env, cfg *config, inputCmd *command) (*oldWrapperConfig, error) {
	absWrapperPath, err := getAbsWrapperPath(env, inputCmd)
	if err != nil {
		return nil, err
	}
	absOldWrapperPath := cfg.oldWrapperPath
	if !filepath.IsAbs(absOldWrapperPath) {
		absOldWrapperPath = filepath.Join(filepath.Dir(absWrapperPath), cfg.oldWrapperPath)
	}
	oldWrapperContentBytes, err := ioutil.ReadFile(absOldWrapperPath)
	if err != nil {
		return nil, wrapErrorwithSourceLocf(err, "failed to read old wrapper")
	}
	oldWrapperContent := string(oldWrapperContentBytes)
	return &oldWrapperConfig{
		WrapperPath:       absWrapperPath,
		CmdPath:           inputCmd.Path,
		OldWrapperContent: oldWrapperContent,
	}, nil
}

func callOldShellWrapper(env env, cfg *oldWrapperConfig, inputCmd *command, filepattern string, stdout io.Writer, stderr io.Writer) (exitCode int, err error) {
	oldWrapperContent := cfg.OldWrapperContent
	oldWrapperContent = regexp.MustCompile(`(?m)^exec\b`).ReplaceAllString(oldWrapperContent, "exec_mock")
	oldWrapperContent = regexp.MustCompile(`\$EXEC`).ReplaceAllString(oldWrapperContent, "exec_mock")
	// TODO: Use strings.ReplaceAll once cros sdk uses golang >= 1.12
	oldWrapperContent = strings.Replace(oldWrapperContent, "$0", cfg.CmdPath, -1)
	cfg.OldWrapperContent = oldWrapperContent
	mockFile, err := ioutil.TempFile("", filepattern)
	if err != nil {
		return 0, wrapErrorwithSourceLocf(err, "failed to create tempfile")
	}
	defer os.Remove(mockFile.Name())

	const mockTemplate = `
EXEC=exec

function exec_mock {
	echo command:${*}.EnvUpdate: 1>&2
	{{if .MockCmds}}
	echo '{{(index .CmdResults 0).Stdout}}'
	echo '{{(index .CmdResults 0).Stderr}}' 1>&2
	exit {{(index .CmdResults 0).Exitcode}}
	{{else}}
	$EXEC ${*}
	{{end}}
}

{{.OldWrapperContent}}
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

	// Note: Using a self executable wrapper does not work due to a race condition
	// on unix systems. See https://github.com/golang/go/issues/22315
	oldWrapperCmd := &command{
		Path:       "/bin/sh",
		Args:       append([]string{mockFile.Name()}, inputCmd.Args...),
		EnvUpdates: inputCmd.EnvUpdates,
	}
	return wrapSubprocessErrorWithSourceLoc(oldWrapperCmd, env.run(oldWrapperCmd, stdout, stderr))
}

func callOldPythonWrapper(env env, cfg *oldWrapperConfig, inputCmd *command, filepattern string, stdout io.Writer, stderr io.Writer) (exitCode int, err error) {
	oldWrapperContent := cfg.OldWrapperContent
	// TODO: Use strings.ReplaceAll once cros sdk uses golang >= 1.12
	oldWrapperContent = strings.Replace(oldWrapperContent, "from __future__ import print_function", "", -1)
	// Replace sets with lists to make our comparisons deterministic
	oldWrapperContent = strings.Replace(oldWrapperContent, "set(", "ListSet(", -1)
	oldWrapperContent = strings.Replace(oldWrapperContent, "if __name__ == '__main__':", "def runMain():", -1)
	oldWrapperContent = strings.Replace(oldWrapperContent, "__file__", "'"+cfg.WrapperPath+"'", -1)
	cfg.OldWrapperContent = oldWrapperContent

	mockFile, err := ioutil.TempFile("", filepattern)
	if err != nil {
		return 0, wrapErrorwithSourceLocf(err, "failed to create tempfile")
	}
	defer os.Remove(mockFile.Name())

	const mockTemplate = `
from __future__ import print_function

class ListSet:
	def __init__(self, values):
		self.values = list(values)
	def __contains__(self, key):
		return self.values.__contains__(key)
	def __iter__(self):
		return self.values.__iter__()
	def __nonzero__(self):
		return len(self.values) > 0
	def add(self, value):
		if value not in self.values:
			self.values.append(value)
	def discard(self, value):
		if value in self.values:
			self.values.remove(value)
	def intersection(self, values):
		return ListSet([value for value in self.values if value in values])

{{.OldWrapperContent}}
import subprocess

init_env = os.environ.copy()

mockResults = [{{range .CmdResults}} {
	'stdout': '{{.Stdout}}',
	'stderr': '{{.Stderr}}',
	'exitcode': {{.Exitcode}},
},{{end}}]

def serialize_cmd(args):
	current_env = os.environ
	envupdate = [k + "=" + current_env.get(k, '') for k in set(list(current_env.keys()) + list(init_env.keys())) if current_env.get(k, '') != init_env.get(k, '')]
	print('command:%s.EnvUpdate:%s' % (' '.join(args), ' '.join(envupdate)), file=sys.stderr)

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

def popen_mock(args, stdout=None, stderr=None):
	serialize_cmd(args)
	{{if .MockCmds}}
	result = mockResults.pop(0)
	if stdout is None:
		print(result['stdout'], file=sys.stdout)
	if stderr is None:
		print(result['stderr'], file=sys.stderr)

	class MockResult:
		def __init__(self, returncode):
			self.returncode = returncode
		def wait(self):
			return self.returncode
		def communicate(self):
			return (result['stdout'], result['stderr'])

	return MockResult(result['exitcode'])
	{{else}}
	return old_popen(args)
	{{end}}

old_popen = subprocess.Popen
subprocess.Popen = popen_mock

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

runMain()
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

	// Note: Using a self executable wrapper does not work due to a race condition
	// on unix systems. See https://github.com/golang/go/issues/22315
	oldWrapperCmd := &command{
		Path:       "/usr/bin/python2",
		Args:       append([]string{"-S", mockFile.Name()}, inputCmd.Args...),
		EnvUpdates: inputCmd.EnvUpdates,
	}
	return wrapSubprocessErrorWithSourceLoc(oldWrapperCmd, env.run(oldWrapperCmd, stdout, stderr))
}
