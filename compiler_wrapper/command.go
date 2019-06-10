package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"sort"
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
	execCmd.Env = env.environ()
	execCmd.Dir = env.getwd()
	return execCmd
}

// TODO: Move to test once we no longer compare the calculated command against
// the command produced by the old wrapper in the released binary.
func (actual *command) verifySimilarTo(expected *command) error {
	var differences []string
	if actual.path != expected.path {
		differences = append(differences, fmt.Sprintf("Paths are different. Expected: %q. Actual: %q", expected.path, actual.path))
	}

	if !reflect.DeepEqual(actual.args, expected.args) {
		differences = append(differences, fmt.Sprintf("Args are different. Expected: %q. Actual: %q", expected.args, actual.args))
	}

	// Sort the environment as we don't care in which order
	// it was modified.
	actualEnvUpdates := actual.envUpdates
	sort.Strings(actualEnvUpdates)
	expectedEnvUpdates := expected.envUpdates
	sort.Strings(expectedEnvUpdates)

	if !reflect.DeepEqual(actualEnvUpdates, expectedEnvUpdates) {
		differences = append(differences, fmt.Sprintf("Env updates are different. Expected: %q. Actual: %q", expectedEnvUpdates, actualEnvUpdates))
	}

	if len(differences) > 0 {
		return errors.New("commands differ:\n" + strings.Join(differences, "\n"))
	}
	return nil
}

func newCommandBuilder(env env, cmd *command) (*commandBuilder, error) {
	basename := filepath.Base(cmd.path)
	nameParts := strings.Split(basename, "-")
	if len(nameParts) != 5 {
		return nil, fmt.Errorf("expected 5 parts in the compiler name. Actual: %s", basename)
	}

	compiler := nameParts[4]
	var compilerType compilerType
	switch {
	case strings.HasPrefix(compiler, "clang"):
		compilerType = clangType
	case strings.HasPrefix(compiler, "gcc"):
		compilerType = gccType
	case strings.HasPrefix(compiler, "g++"):
		compilerType = gccType
	default:
		return nil, fmt.Errorf("expected clang or gcc. Actual: %s", basename)
	}
	return &commandBuilder{
		path: cmd.path,
		args: createBuilderArgs( /*fromUser=*/ true, cmd.args),
		env:  env,
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
}

type builderArg struct {
	Value    string
	FromUser bool
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
		builderArgs[i] = builderArg{Value: arg, FromUser: fromUser}
	}
	return builderArgs
}

func (builder *commandBuilder) wrapPath(path string) {
	builder.args = append([]builderArg{{Value: builder.path, FromUser: false}}, builder.args...)
	builder.path = path
}

func (builder *commandBuilder) addPreUserArgs(args ...string) {
	index := 0
	for _, arg := range builder.args {
		if arg.FromUser {
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
				Value:    newArg,
				FromUser: arg.FromUser,
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
		cmdArgs[i] = builderArg.Value
	}
	return &command{
		path:       builder.path,
		args:       cmdArgs,
		envUpdates: builder.envUpdates,
	}
}
