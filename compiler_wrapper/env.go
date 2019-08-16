// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"strings"
	"syscall"
)

type env interface {
	getenv(key string) string
	environ() []string
	getwd() string
	stdin() io.Reader
	stdout() io.Writer
	stderr() io.Writer
	run(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error
	exec(cmd *command) error
}

type processEnv struct {
	wd string
}

func newProcessEnv() (env, error) {
	wd, err := os.Getwd()
	if err != nil {
		return nil, wrapErrorwithSourceLocf(err, "failed to read working directory")
	}
	return &processEnv{wd: wd}, nil
}

var _ env = (*processEnv)(nil)

func (env *processEnv) getenv(key string) string {
	return os.Getenv(key)
}

func (env *processEnv) environ() []string {
	return os.Environ()
}

func (env *processEnv) getwd() string {
	return env.wd
}

func (env *processEnv) stdin() io.Reader {
	return os.Stdin
}

func (env *processEnv) stdout() io.Writer {
	return os.Stdout
}

func (env *processEnv) stderr() io.Writer {
	return os.Stderr
}

func (env *processEnv) exec(cmd *command) error {
	execCmd := newExecCmd(env, cmd)
	return syscall.Exec(execCmd.Path, execCmd.Args, execCmd.Env)
}

func (env *processEnv) run(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
	execCmd := newExecCmd(env, cmd)
	execCmd.Stdin = stdin
	execCmd.Stdout = stdout
	execCmd.Stderr = stderr
	_, stdinIsFile := stdin.(*os.File)
	_, stdinIsBytesReader := stdin.(*bytes.Reader)
	if stdin != nil && !stdinIsFile && !stdinIsBytesReader {
		// We can't use execCmd.Run() here as that blocks if stdin blocks,
		// even if the underlying process has already terminated. We care
		// especially about the case when stdin is an io.TeeReader for os.Stdin.
		// See https://github.com/golang/go/issues/7990 for more details.
		if err := execCmd.Start(); err != nil {
			return err
		}
		if _, err := execCmd.Process.Wait(); err != nil {
			return err
		}
		// Closing Stdin here as we didn't wait for the read to finish via
		// execCmd.Wait to prevent race conditions.
		os.Stdin.Close()
		return nil
	}
	return execCmd.Run()
}

type commandRecordingEnv struct {
	env
	stdinReader io.Reader
	cmdResults  []*commandResult
}
type commandResult struct {
	Cmd      *command `json:"cmd"`
	Stdout   string   `json:"stdout,omitempty"`
	Stderr   string   `json:"stderr,omitempty"`
	ExitCode int      `json:"exitcode,omitempty"`
}

var _ env = (*commandRecordingEnv)(nil)

func (env *commandRecordingEnv) stdin() io.Reader {
	return env.stdinReader
}

func (env *commandRecordingEnv) exec(cmd *command) error {
	// Note: We treat exec the same as run so that we can do work
	// after the call.
	return env.run(cmd, env.stdin(), env.stdout(), env.stderr())
}

func (env *commandRecordingEnv) run(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
	stdoutBuffer := &bytes.Buffer{}
	stderrBuffer := &bytes.Buffer{}
	err := env.env.run(cmd, stdin, io.MultiWriter(stdout, stdoutBuffer), io.MultiWriter(stderr, stderrBuffer))
	if exitCode, ok := getExitCode(err); ok {
		env.cmdResults = append(env.cmdResults, &commandResult{
			Cmd:      cmd,
			Stdout:   stdoutBuffer.String(),
			Stderr:   stderrBuffer.String(),
			ExitCode: exitCode,
		})
	}
	return err
}

type printingEnv struct {
	env
}

var _env = (*printingEnv)(nil)

func (env *printingEnv) exec(cmd *command) error {
	printCmd(env, cmd)
	return env.env.exec(cmd)
}

func (env *printingEnv) run(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
	printCmd(env, cmd)
	return env.env.run(cmd, stdin, stdout, stderr)
}

func printCmd(env env, cmd *command) {
	fmt.Fprintf(env.stderr(), "cd '%s' &&", env.getwd())
	if len(cmd.EnvUpdates) > 0 {
		fmt.Fprintf(env.stderr(), " env '%s'", strings.Join(cmd.EnvUpdates, "' '"))
	}
	fmt.Fprintf(env.stderr(), " '%s'", getAbsCmdPath(env, cmd))
	if len(cmd.Args) > 0 {
		fmt.Fprintf(env.stderr(), " '%s'", strings.Join(cmd.Args, "' '"))
	}
	io.WriteString(env.stderr(), "\n")
}
