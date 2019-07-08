package main

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"path/filepath"
	"strings"
	"testing"
	"text/template"
)

func TestNoForwardToOldWrapperBecauseOfEnv(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		testEnvs := []string{"PATH=abc"}
		for _, testEnv := range testEnvs {
			ctx.env = []string{testEnv}
			forwarded := false
			ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
				if isForwardToOldWrapperCmd(cmd) {
					forwarded = true
				}
				return nil
			}
			ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(clangX86_64)))
			if forwarded {
				t.Errorf("forwarded to old wrapper for env %s", testEnv)
			}
		}
	})
}

func TestForwardToOldWrapperBecauseOfEnv(t *testing.T) {
	withForwardToOldWrapperTestContext(t, func(ctx *testContext) {
		testEnvs := []string{
			"FORCE_DISABLE_WERROR=abc",
			"GETRUSAGE=abc",
			"BISECT_STAGE=abc",
		}
		for _, testEnv := range testEnvs {
			ctx.env = []string{testEnv}
			forwarded := false
			ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
				forwarded = true
				if !isForwardToOldWrapperCmd(cmd) {
					return newErrorwithSourceLocf("expected call to old wrapper. Got: %s", cmd.path)
				}
				return nil
			}
			ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(clangX86_64)))
			if !forwarded {
				t.Errorf("not forwarded to old wrapper for env %s", testEnv)
			}
		}
	})
}

func TestForwardStdOutAndStderrFromOldWrapperOnSuccess(t *testing.T) {
	withForwardToOldWrapperTestContext(t, func(ctx *testContext) {
		ctx.env = []string{"BISECT_STAGE=abc"}
		ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
			fmt.Fprint(stdout, "somemessage")
			fmt.Fprint(stderr, "someerror")
			return nil
		}

		ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(clangX86_64)))
		if ctx.stdoutString() != "somemessage" {
			t.Errorf("stdout was not exactly forwarded. Got: %s", ctx.stdoutString())
		}
		if ctx.stderrString() != "someerror" {
			t.Errorf("stderr was not exactly forwarded. Got: %s", ctx.stderrString())
		}
	})
}

func TestReportExitCodeErrorsWhenForwardingToOldWrapper(t *testing.T) {
	withForwardToOldWrapperTestContext(t, func(ctx *testContext) {
		ctx.env = []string{"BISECT_STAGE=abc"}
		ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
			fmt.Fprint(stderr, "someerror")
			return newExitCodeError(2)
		}

		exitCode := callCompiler(ctx, ctx.cfg, ctx.newCommand(clangX86_64))
		if exitCode != 2 {
			t.Fatalf("Expected exit code 2. Got %d", exitCode)
		}
		if err := verifyNonInternalError(ctx.stderrString(), "someerror"); err != nil {
			t.Fatal(err)
		}
	})
}

func TestReportGeneralErrorsWhenForwardingToOldWrapper(t *testing.T) {
	withForwardToOldWrapperTestContext(t, func(ctx *testContext) {
		ctx.env = []string{"BISECT_STAGE=abc"}
		ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
			fmt.Fprint(stderr, "someoldwrappererror")
			return errors.New("someerror")
		}

		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg, ctx.newCommand(clangX86_64)))
		if err := verifyInternalError(stderr); err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(stderr, "someerror") {
			t.Errorf("error message was not forwarded. Got: %s", stderr)
		}
		if !strings.Contains(stderr, "someoldwrappererror") {
			t.Errorf("stderr was not forwarded. Got: %s", stderr)
		}
	})
}

func TestCompareToOldWrapperCompilerCommand(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		pathSuffix := ""
		extraArgs := []string{}
		exitCode := 0

		ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
			writeMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path:     cmd.path + pathSuffix,
						Args:     append(cmd.args, extraArgs...),
						ExitCode: exitCode,
					},
				},
			})
			return nil
		}

		// Note: This will cause only the compiler command.
		inputCmd := ctx.newCommand(gccX86_64)

		ctx.stderrBuffer.Reset()
		pathSuffix = "xyz"
		extraArgs = nil
		exitCode = 0
		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: path") {
			t.Errorf("expected path difference error. Got: %s", stderr)
		}

		ctx.stderrBuffer.Reset()
		pathSuffix = ""
		extraArgs = []string{"xyz"}
		exitCode = 0
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: args") {
			t.Errorf("expected args difference error. Got: %s", stderr)
		}

		ctx.stderrBuffer.Reset()
		pathSuffix = ""
		extraArgs = nil
		exitCode = 1
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: exit code") {
			t.Errorf("expected exit code difference error. Got: %s", stderr)
		}

		pathSuffix = ""
		extraArgs = nil
		exitCode = 0
		ctx.must(callCompiler(ctx, ctx.cfg, inputCmd))
	})
}

func TestCompareToOldWrapperNestedCommand(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		pathSuffix := ""
		extraArgs := []string{}
		wrapperCfg := &mockWrapperConfig{}

		ctx.cmdMock = func(cmd *command, stdout io.Writer, stderr io.Writer) error {
			isNestedCmd := len(wrapperCfg.Cmds) == 0
			var wrapperCmd *mockWrapperCmd
			if isNestedCmd {
				wrapperCmd = &mockWrapperCmd{
					Path: cmd.path + pathSuffix,
					Args: append(cmd.args, extraArgs...),
				}
			} else {
				wrapperCmd = &mockWrapperCmd{
					Path: cmd.path,
					Args: cmd.args,
				}
			}
			wrapperCfg.Cmds = append(wrapperCfg.Cmds, wrapperCmd)
			if !isNestedCmd {
				writeMockWrapper(ctx, wrapperCfg)
			}
			return nil
		}

		// Note: This will cause a nested command call.
		inputCmd := ctx.newCommand(clangX86_64, "-Xclang-path=somedir", mainCc)

		ctx.stderrBuffer.Reset()
		wrapperCfg = &mockWrapperConfig{}
		pathSuffix = "xyz"
		extraArgs = nil
		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: path") {
			t.Errorf("expected path difference error. Got: %s", stderr)
		}
		if !strings.Contains(stderr, "Index 1: none") {
			t.Errorf("expected no difference for cmd index 1. Got: %s", stderr)
		}

		ctx.stderrBuffer.Reset()
		wrapperCfg = &mockWrapperConfig{}
		pathSuffix = ""
		extraArgs = []string{"xyz"}
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: args") {
			t.Errorf("expected args difference error. Got: %s", stderr)
		}
		if !strings.Contains(stderr, "Index 1: none") {
			t.Errorf("expected no difference for cmd index 1. Got: %s", stderr)
		}

		wrapperCfg = &mockWrapperConfig{}
		pathSuffix = ""
		extraArgs = nil
		ctx.must(callCompiler(ctx, ctx.cfg, inputCmd))
	})
}

func withForwardToOldWrapperTestContext(t *testing.T, work func(ctx *testContext)) {
	withTestContext(t, func(ctx *testContext) {
		// Need to make sure the old wrapper file exists as oldwrapper.go
		// tries to read it.
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "somewrapper")
		ctx.writeFile(ctx.cfg.oldWrapperPath, "")
		work(ctx)
	})
}

func writeMockWrapper(ctx *testContext, cfg *mockWrapperConfig) {
	const mockTemplate = `
from __future__ import print_function
import os
import sys
import subprocess

mockCmds = [{{range .Cmds}} {
	'path': '{{.Path}}',
	'args': [{{range .Args}}'{{.}}',{{end}}],
	'exitcode': {{.ExitCode}},
},{{end}}]

def execv_impl(binary, args):
	cmd = mockCmds.pop(0)
	sys.exit(cmd['exitcode'])
os.execv = execv_impl

def check_output_impl(args):
	cmd = mockCmds.pop(0)
	if cmd['exitcode']:
		raise subprocess.CalledProcessError(cmd['exitcode'])
	return ""
subprocess.check_output = check_output_impl

def main():
	while len(mockCmds) > 1:
		subprocess.check_output([mockCmds[0]['path']] + mockCmds[0]['args'])

	os.execv(mockCmds[0]['path'], [mockCmds[0]['path']] + mockCmds[0]['args'])

if __name__ == '__main__':
	sys.exit(main())
`
	tmpl, err := template.New("mock").Parse(mockTemplate)
	if err != nil {
		ctx.t.Fatalf("failed to parse old wrapper template. Error: %s", err)
	}
	buf := bytes.Buffer{}
	if err := tmpl.Execute(&buf, cfg); err != nil {
		ctx.t.Fatalf("failed to execute the template. Error: %s", err)
	}
	ctx.writeFile(ctx.cfg.oldWrapperPath, buf.String())
}

// Note: Fields have to be uppercase so that they can be used with template.
type mockWrapperConfig struct {
	Cmds []*mockWrapperCmd
}

// Note: Fields have to be uppercase so that they can be used with template.
type mockWrapperCmd struct {
	Path     string
	Args     []string
	ExitCode int
}
