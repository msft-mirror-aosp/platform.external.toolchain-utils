package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type command struct {
	path       string
	args       []string
	envUpdates []string
}

func newProcessCommand() *command {
	return &command{
		path: os.Args[0],
		args: os.Args[1:],
	}
}

func newExecCmd(env env, cmd *command) *exec.Cmd {
	execCmd := exec.Command(cmd.path, cmd.args...)
	execCmd.Env = append(env.environ(), cmd.envUpdates...)
	ensurePathEnv(execCmd)
	execCmd.Dir = env.getwd()
	return execCmd
}

func ensurePathEnv(cmd *exec.Cmd) {
	for _, env := range cmd.Env {
		if strings.HasPrefix(env, "PATH=") {
			return
		}
	}
	cmd.Env = append(cmd.Env, "PATH=")
}

func newCommandBuilder(env env, cfg *config, cmd *command) (*commandBuilder, error) {
	basename := filepath.Base(cmd.path)
	nameParts := strings.Split(basename, "-")
	if len(nameParts) != 5 {
		return nil, newErrorwithSourceLocf("expected 5 parts in the compiler name. Actual: %s", basename)
	}

	compiler := nameParts[4]
	var compilerType compilerType
	switch {
	case strings.HasPrefix(compiler, "clang"):
		compilerType = clangType
	default:
		compilerType = gccType
	}
	absWrapperDir, err := getAbsWrapperDir(env, cmd.path)
	if err != nil {
		return nil, err
	}
	rootPath := filepath.Join(absWrapperDir, cfg.rootRelPath)
	return &commandBuilder{
		path:     cmd.path,
		args:     createBuilderArgs( /*fromUser=*/ true, cmd.args),
		env:      env,
		cfg:      cfg,
		rootPath: rootPath,
		target: builderTarget{
			target:       strings.Join(nameParts[:4], "-"),
			arch:         nameParts[0],
			vendor:       nameParts[1],
			sys:          nameParts[2],
			abi:          nameParts[3],
			compiler:     compiler,
			compilerType: compilerType,
		},
	}, nil
}

type commandBuilder struct {
	path       string
	target     builderTarget
	args       []builderArg
	envUpdates []string
	env        env
	cfg        *config
	rootPath   string
}

type builderArg struct {
	value    string
	fromUser bool
}

type compilerType int32

const (
	gccType compilerType = iota
	clangType
)

type builderTarget struct {
	target       string
	arch         string
	vendor       string
	sys          string
	abi          string
	compiler     string
	compilerType compilerType
}

func createBuilderArgs(fromUser bool, args []string) []builderArg {
	builderArgs := make([]builderArg, len(args))
	for i, arg := range args {
		builderArgs[i] = builderArg{value: arg, fromUser: fromUser}
	}
	return builderArgs
}

func (builder *commandBuilder) clone() *commandBuilder {
	return &commandBuilder{
		path:     builder.path,
		args:     append([]builderArg{}, builder.args...),
		env:      builder.env,
		cfg:      builder.cfg,
		rootPath: builder.rootPath,
		target:   builder.target,
	}
}

func (builder *commandBuilder) wrapPath(path string) {
	builder.args = append([]builderArg{{value: builder.path, fromUser: false}}, builder.args...)
	builder.path = path
}

func (builder *commandBuilder) addPreUserArgs(args ...string) {
	index := 0
	for _, arg := range builder.args {
		if arg.fromUser {
			break
		}
		index++
	}
	builder.args = append(builder.args[:index], append(createBuilderArgs( /*fromUser=*/ false, args), builder.args[index:]...)...)
}

func (builder *commandBuilder) addPostUserArgs(args ...string) {
	builder.args = append(builder.args, createBuilderArgs( /*fromUser=*/ false, args)...)
}

// Allows to map and filter arguments. Filters when the callback returns an empty string.
func (builder *commandBuilder) transformArgs(transform func(arg builderArg) string) {
	// See https://github.com/golang/go/wiki/SliceTricks
	newArgs := builder.args[:0]
	for _, arg := range builder.args {
		newArg := transform(arg)
		if newArg != "" {
			newArgs = append(newArgs, builderArg{
				value:    newArg,
				fromUser: arg.fromUser,
			})
		}
	}
	builder.args = newArgs
}

func (builder *commandBuilder) updateEnv(updates ...string) {
	builder.envUpdates = append(builder.envUpdates, updates...)
}

func (builder *commandBuilder) build() *command {
	cmdArgs := make([]string, len(builder.args))
	for i, builderArg := range builder.args {
		cmdArgs[i] = builderArg.value
	}
	return &command{
		path:       builder.path,
		args:       cmdArgs,
		envUpdates: builder.envUpdates,
	}
}
