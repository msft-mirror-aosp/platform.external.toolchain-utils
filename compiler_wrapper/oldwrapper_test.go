// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"fmt"
	"io"
	"path/filepath"
	"strings"
	"testing"
	"text/template"
)

func TestCompareToOldPythonWrapperCompilerCommand(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		pathSuffix := ""
		extraArgs := []string{}
		exitCode := 0
		newWrapperExitCode := 0

		reset := func() {
			ctx.stderrBuffer.Reset()
			pathSuffix = ""
			extraArgs = []string{}
			exitCode = 0
			newWrapperExitCode = 0
		}

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			writePythonMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path:     cmd.Path + pathSuffix,
						Args:     append(cmd.Args, extraArgs...),
						ExitCode: exitCode,
					},
				},
			})
			if newWrapperExitCode != 0 {
				return newExitCodeError(newWrapperExitCode)
			}
			return nil
		}

		// Note: This will cause only the compiler command.
		inputCmd := ctx.newCommand(gccX86_64)

		reset()
		pathSuffix = "xyz"
		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: path") {
			t.Errorf("expected path difference error. Got: %s", stderr)
		}

		reset()
		extraArgs = []string{"xyz"}
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: args") {
			t.Errorf("expected args difference error. Got: %s", stderr)
		}

		reset()
		exitCode = 1
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "exit codes differ: old 1, new 0") {
			t.Errorf("expected exit code difference error. Got: %s", stderr)
		}

		reset()
		newWrapperExitCode = 1
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "exit codes differ: old 0, new 1") {
			t.Errorf("expected exit code difference error. Got: %s", stderr)
		}

		reset()
		ctx.must(callCompiler(ctx, ctx.cfg, inputCmd))
	})
}

func TestCompareToOldPythonWrapperNestedCommand(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		pathSuffix := ""
		extraArgs := []string{}
		wrapperCfg := &mockWrapperConfig{}

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			isNestedCmd := len(wrapperCfg.Cmds) == 0
			var wrapperCmd *mockWrapperCmd
			if isNestedCmd {
				wrapperCmd = &mockWrapperCmd{
					Path: cmd.Path + pathSuffix,
					Args: append(cmd.Args, extraArgs...),
				}
			} else {
				wrapperCmd = &mockWrapperCmd{
					Path: cmd.Path,
					Args: cmd.Args,
				}
			}
			wrapperCfg.Cmds = append(wrapperCfg.Cmds, wrapperCmd)
			if !isNestedCmd {
				writePythonMockWrapper(ctx, wrapperCfg)
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

func TestCompareToOldShellWrapperCompilerCommand(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		pathSuffix := ""
		extraArgs := []string{}
		exitCode := 0
		newWrapperExitCode := 0

		reset := func() {
			ctx.stderrBuffer.Reset()
			pathSuffix = ""
			extraArgs = []string{}
			exitCode = 0
			newWrapperExitCode = 0
		}

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			writeShellMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path:     cmd.Path + pathSuffix,
						Args:     append(cmd.Args, extraArgs...),
						ExitCode: exitCode,
					},
				},
			})
			if newWrapperExitCode != 0 {
				return newExitCodeError(newWrapperExitCode)
			}
			return nil
		}

		// Note: This will cause only the compiler command.
		inputCmd := ctx.newCommand(gccX86_64)

		reset()
		pathSuffix = "xyz"
		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: path") {
			t.Errorf("expected path difference error. Got: %s", stderr)
		}

		reset()
		extraArgs = []string{"xyz"}
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "Index 0: args") {
			t.Errorf("expected args difference error. Got: %s", stderr)
		}

		reset()
		exitCode = 1
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "exit codes differ: old 1, new 0") {
			t.Errorf("expected exit code difference error. Got: %s", stderr)
		}

		reset()
		newWrapperExitCode = 1
		stderr = ctx.mustFail(callCompiler(ctx, ctx.cfg, inputCmd))
		if !strings.Contains(stderr, "exit codes differ: old 0, new 1") {
			t.Errorf("expected exit code difference error. Got: %s", stderr)
		}

		reset()
		ctx.must(callCompiler(ctx, ctx.cfg, inputCmd))

		reset()
		ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, " spaces ")))
	})
}

func TestCompareToOldWrapperEscapeStdoutAndStderr(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			io.WriteString(stdout, "a\n'b'\\")
			io.WriteString(stderr, "c\n'd'\\")
			writePythonMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path: cmd.Path,
						Args: cmd.Args,
					},
				},
			})
			return nil
		}

		ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
		if ctx.stdoutString() != "a\n'b'\\" {
			t.Errorf("unexpected stdout. Got: %s", ctx.stdoutString())
		}
		if ctx.stderrString() != "c\n'd'\\" {
			t.Errorf("unexpected stderr. Got: %s", ctx.stderrString())
		}
	})
}

func TestCompareToOldWrapperSupportUtf8InStdoutAndStderr(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			io.WriteString(stdout, "©")
			io.WriteString(stderr, "®")
			writePythonMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path: cmd.Path,
						Args: cmd.Args,
					},
				},
			})
			return nil
		}

		ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
		if ctx.stdoutString() != "©" {
			t.Errorf("unexpected stdout. Got: %s", ctx.stdoutString())
		}
		if ctx.stderrString() != "®" {
			t.Errorf("unexpected stderr. Got: %s", ctx.stderrString())
		}
	})
}

func TestCompareToOldPythonWrapperArgumentsWithSpaces(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			writePythonMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path: cmd.Path,
						Args: cmd.Args,
					},
				},
			})
			return nil
		}

		ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, "a b", "c", mainCc)))
	})
}

func TestCompareToOldShellWrapperArgumentsWithSpaces(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			writeShellMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path: cmd.Path,
						Args: cmd.Args,
					},
				},
			})
			return nil
		}

		ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, "a b", "c", mainCc)))
	})
}

func TestForwardStdinWhenUsingOldWrapper(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		io.WriteString(&ctx.stdinBuffer, "someinput")
		ctx.cfg.mockOldWrapperCmds = false
		ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "fakewrapper")

		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			writeShellMockWrapper(ctx, &mockWrapperConfig{
				Cmds: []*mockWrapperCmd{
					{
						Path: cmd.Path,
						Args: cmd.Args,
					},
				},
			})
			stdinStr := ctx.readAllString(stdin)
			if stdinStr != "someinput" {
				return fmt.Errorf("unexpected stdin. Got: %s", stdinStr)
			}
			return nil
		}

		ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, "-", mainCc)))
	})
}

func writePythonMockWrapper(ctx *testContext, cfg *mockWrapperConfig) {
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

func writeShellMockWrapper(ctx *testContext, cfg *mockWrapperConfig) {
	const mockTemplate = `#!/bin/sh
EXEC=fake_exec

function fake_exec {
	exit {{(index .Cmds 0).ExitCode}}
}

$EXEC "{{(index .Cmds 0).Path}}"{{range (index .Cmds 0).Args}} "{{.}}"{{end}}
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
