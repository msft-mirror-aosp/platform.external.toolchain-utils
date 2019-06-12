#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Clang_Tidy_Warn Warning Patterns data

This file stores the warn_patterns dictionary used in clang_tidy_warn.py and
its dependencies. It has been put into this file for easier navigation and
understanding of the original file.
"""

from collections import namedtuple

# Create Severity class, where each Severity level is a named tuple
# value and proto_value exist because value adheres to the original severity
# ordering, while protobuffer severity values are edited so that UNKNOWN=0
# because this is best practice for enums. proto_value is only used for
# generating Warning messages, and value should be used elsewhere.
Severity = namedtuple(
    'Severity', ['proto_value', 'value', 'color', 'column_header', 'header'])
Severity.UNKNOWN = Severity(
    proto_value=0,
    value=7,
    color='lightblue',
    column_header='Unknown',
    header='Unknown warnings')
Severity.FIXMENOW = Severity(
    proto_value=1,
    value=0,
    color='fuschia',
    column_header='FixNow',
    header='Critical warnings, fix me now')
Severity.HIGH = Severity(
    proto_value=2,
    value=1,
    color='red',
    column_header='High',
    header='High severity warnings')
Severity.MEDIUM = Severity(
    proto_value=3,
    value=2,
    color='orange',
    column_header='Medium',
    header='Medium severity warnings')
Severity.LOW = Severity(
    proto_value=4,
    value=3,
    color='yellow',
    column_header='Low',
    header='Low severity warnings')
Severity.ANALYZER = Severity(
    proto_value=5,
    value=4,
    color='hotpink',
    column_header='Analyzer',
    header='Clang-Analyzer warnings')
Severity.TIDY = Severity(
    proto_value=6,
    value=5,
    color='peachpuff',
    column_header='Tidy',
    header='Clang-Tidy warnings')
Severity.HARMLESS = Severity(
    proto_value=7,
    value=6,
    color='limegreen',
    column_header='Harmless',
    header='Harmless warnings')
Severity.SKIP = Severity(
    proto_value=8,
    value=8,
    color='grey',
    column_header='Unhandled',
    header='Unhandled warnings')

Severity.levels = [
    Severity.FIXMENOW, Severity.HIGH, Severity.MEDIUM, Severity.LOW,
    Severity.ANALYZER, Severity.TIDY, Severity.HARMLESS, Severity.UNKNOWN,
    Severity.SKIP
]
# HTML relies on ordering by value. Sort here to ensure that this is proper
Severity.levels = sorted(Severity.levels, key=lambda severity: severity.value)


def tidy_warn_pattern(description, pattern):
  return {
      'category': 'C/C++',
      'severity': Severity.TIDY,
      'description': 'clang-tidy ' + description,
      'patterns': [r'.*: .+\[' + pattern + r'\]$']
  }


def simple_tidy_warn_pattern(description):
  return tidy_warn_pattern(description, description)


def group_tidy_warn_pattern(description):
  return tidy_warn_pattern(description, description + r'-.+')


warn_patterns = [
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer Security warning',
        'patterns': [r".*: warning: .+\[clang-analyzer-security.*\]"]
    },
    {
        'category':
            'make',
        'severity':
            Severity.MEDIUM,
        'description':
            'make: overriding commands/ignoring old commands',
        'patterns': [
            r".*: warning: overriding commands for target .+",
            r".*: warning: ignoring old commands for target .+"
        ]
    },
    {
        'category': 'make',
        'severity': Severity.HIGH,
        'description': 'make: LOCAL_CLANG is false',
        'patterns': [r".*: warning: LOCAL_CLANG is set to false"]
    },
    {
        'category':
            'make',
        'severity':
            Severity.HIGH,
        'description':
            'SDK App using platform shared library',
        'patterns': [
            r".*: warning: .+ \(.*app:sdk.*\) should not link to .+ "
            r"\(native:platform\)"
        ]
    },
    {
        'category':
            'make',
        'severity':
            Severity.HIGH,
        'description':
            'System module linking to a vendor module',
        'patterns': [
            r".*: warning: .+ \(.+\) should not link to .+ \(partition:.+\)"
        ]
    },
    {
        'category': 'make',
        'severity': Severity.MEDIUM,
        'description': 'Invalid SDK/NDK linking',
        'patterns': [r".*: warning: .+ \(.+\) should not link to .+ \(.+\)"]
    },
    {
        'category': 'make',
        'severity': Severity.MEDIUM,
        'description': 'Duplicate header copy',
        'patterns': [r".*: warning: Duplicate header copy: .+"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-Wimplicit-function-declaration',
        'description':
            'Implicit function declaration',
        'patterns': [
            r".*: warning: implicit declaration of function .+",
            r".*: warning: implicitly declaring library function"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.SKIP,
        'description': 'skip, conflicting types for ...',
        'patterns': [r".*: warning: conflicting types for '.+'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-Wtype-limits',
        'description':
            'Expression always evaluates to true or false',
        'patterns': [
            r".*: warning: comparison is always .+ due to limited range of "
            r"data type",
            r".*: warning: comparison of unsigned .*expression .+ is always "
            r"true",
            r".*: warning: comparison of unsigned .*expression .+ is always "
            r"false"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'description':
            'Potential leak of memory, bad free, use after free',
        'patterns': [
            r".*: warning: Potential leak of memory",
            r".*: warning: Potential memory leak",
            r".*: warning: Memory allocated by alloca\(\) should not be "
            r"deallocated",
            r".*: warning: Memory allocated by .+ should be deallocated by "
            r".+ not .+",
            r".*: warning: 'delete' applied to a pointer that was allocated",
            r".*: warning: Use of memory after it is freed",
            r".*: warning: Argument to .+ is the address of .+ variable",
            r".*: warning: Argument to free\(\) is offset by .+ of memory "
            r"allocated by", r".*: warning: Attempt to .+ released memory"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'description':
            'Use transient memory for control value',
        'patterns': [
            r".*: warning: .+Using such transient memory for the control "
            r"value is .*dangerous."
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'description':
            'Return address of stack memory',
        'patterns': [
            r".*: warning: Address of stack memory .+ returned to caller",
            r".*: warning: Address of stack memory .+ will be a dangling "
            r"reference"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'description':
            'Problem with vfork',
        'patterns': [
            r".*: warning: This .+ is prohibited after a successful vfork",
            r".*: warning: Call to function '.+' is insecure "
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            'infinite-recursion',
        'description':
            'Infinite recursion',
        'patterns': [
            r".*: warning: all paths through this function will call itself"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'description':
            'Potential buffer overflow',
        'patterns': [
            r".*: warning: Size argument is greater than .+ the destination "
            r"buffer", r".*: warning: Potential buffer overflow.",
            r".*: warning: String copy function overflows destination buffer"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Incompatible pointer types',
        'patterns': [
            r".*: warning: assignment from incompatible pointer type",
            r".*: warning: return from incompatible pointer type",
            r".*: warning: passing argument [0-9]+ of '.*' from incompatible "
            r"pointer type",
            r".*: warning: initialization from incompatible pointer type"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-fno-builtin',
        'description':
            'Incompatible declaration of built in function',
        'patterns': [
            r".*: warning: incompatible implicit declaration of built-in "
            r"function .+"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-Wincompatible-library-redeclaration',
        'description':
            'Incompatible redeclaration of library function',
        'patterns': [
            r".*: warning: incompatible redeclaration of library function .+"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'description':
            'Null passed as non-null argument',
        'patterns': [
            r".*: warning: Null passed to a callee that requires a non-null"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wunused-parameter',
        'description': 'Unused parameter',
        'patterns': [r".*: warning: unused parameter '.*'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wunused',
        'description':
            'Unused function, variable, label, comparison, etc.',
        'patterns': [
            r".*: warning: '.+' defined but not used",
            r".*: warning: unused function '.+'",
            r".*: warning: unused label '.+'",
            r".*: warning: relational comparison result unused",
            r".*: warning: lambda capture .* is not used",
            r".*: warning: private field '.+' is not used",
            r".*: warning: unused variable '.+'"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wunused-value',
        'description':
            'Statement with no effect or result unused',
        'patterns': [
            r".*: warning: statement with no effect",
            r".*: warning: expression result unused"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wunused-result',
        'description':
            'Ignoreing return value of function',
        'patterns': [
            r".*: warning: ignoring return value of function .+Wunused-result"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wmissing-field-initializers',
        'description': 'Missing initializer',
        'patterns': [r".*: warning: missing initializer"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wdelete-non-virtual-dtor',
        'description':
            'Need virtual destructor',
        'patterns': [
            r".*: warning: delete called .* has virtual functions but "
            r"non-virtual destructor"
        ]
    },
    {
        'category': 'cont.',
        'severity': Severity.SKIP,
        'description': 'skip, near initialization for ...',
        'patterns': [r".*: warning: \(near initialization for '.+'\)"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wdate-time',
        'description':
            'Expansion of data or time macro',
        'patterns': [
            r".*: warning: expansion of date or time macro is not reproducible"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wformat',
        'description':
            'Format string does not match arguments',
        'patterns': [
            r".*: warning: format '.+' expects type '.+', but argument "
            r"[0-9]+ has type '.+'",
            r".*: warning: more '%' conversions than data arguments",
            r".*: warning: data argument not used by format string",
            r".*: warning: incomplete format specifier",
            r".*: warning: unknown conversion type .* in format",
            r".*: warning: format .+ expects .+ but argument .+Wformat=",
            r".*: warning: field precision should have .+ but argument has "
            r".+Wformat",
            r".*: warning: format specifies type .+ but the argument has "
            r".*type .+Wformat"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wformat-extra-args',
        'description': 'Too many arguments for format string',
        'patterns': [r".*: warning: too many arguments for format"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Too many arguments in call',
        'patterns': [r".*: warning: too many arguments in call to "]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wformat-invalid-specifier',
        'description':
            'Invalid format specifier',
        'patterns': [
            r".*: warning: invalid .+ specifier '.+'.+format-invalid-specifier"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wsign-compare',
        'description':
            'Comparison between signed and unsigned',
        'patterns': [
            r".*: warning: comparison between signed and unsigned",
            r".*: warning: comparison of promoted \~unsigned with unsigned",
            r".*: warning: signed and unsigned type in conditional expression"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Comparison between enum and non-enum',
        'patterns': [
            r".*: warning: enumeral and non-enumeral type in conditional "
            r"expression"
        ]
    },
    {
        'category':
            'libpng',
        'severity':
            Severity.MEDIUM,
        'description':
            'libpng: zero area',
        'patterns': [
            r".*libpng warning: Ignoring attempt to set cHRM RGB triangle "
            r"with zero area"
        ]
    },
    {
        'category': 'aapt',
        'severity': Severity.MEDIUM,
        'description': 'aapt: no comment for public symbol',
        'patterns': [r".*: warning: No comment for public symbol .+"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wmissing-braces',
        'description': 'Missing braces around initializer',
        'patterns': [r".*: warning: missing braces around initializer.*"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.HARMLESS,
        'description': 'No newline at end of file',
        'patterns': [r".*: warning: no newline at end of file"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.HARMLESS,
        'description': 'Missing space after macro name',
        'patterns': [r".*: warning: missing whitespace after the macro name"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'option':
            '-Wcast-align',
        'description':
            'Cast increases required alignment',
        'patterns': [
            r".*: warning: cast from .* to .* increases required alignment .*"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wcast-qual',
        'description':
            'Qualifier discarded',
        'patterns': [
            r".*: warning: passing argument [0-9]+ of '.+' discards "
            r"qualifiers from pointer target type",
            r".*: warning: assignment discards qualifiers from pointer "
            r"target type",
            r".*: warning: passing .+ to parameter of type .+ discards "
            r"qualifiers",
            r".*: warning: assigning to .+ from .+ discards qualifiers",
            r".*: warning: initializing .+ discards qualifiers "
            r".+types-discards-qualifiers",
            r".*: warning: return discards qualifiers from pointer target type"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wunknown-attributes',
        'description': 'Unknown attribute',
        'patterns': [r".*: warning: unknown attribute '.+'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wignored-attributes',
        'description':
            'Attribute ignored',
        'patterns': [
            r".*: warning: '_*packed_*' attribute ignored",
            r".*: warning: attribute declaration must precede definition "
            r".+ignored-attributes"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wvisibility',
        'description':
            'Visibility problem',
        'patterns': [
            r".*: warning: declaration of '.+' will not be visible outside "
            r"of this function"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wattributes',
        'description':
            'Visibility mismatch',
        'patterns': [
            r".*: warning: '.+' declared with greater visibility than the "
            r"type of its field '.+'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Shift count greater than width of type',
        'patterns': [r".*: warning: (left|right) shift count >= width of type"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wextern-initializer',
        'description':
            'extern &lt;foo&gt; is initialized',
        'patterns': [
            r".*: warning: '.+' initialized and declared 'extern'",
            r".*: warning: 'extern' variable has an initializer"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wold-style-declaration',
        'description':
            'Old style declaration',
        'patterns': [
            r".*: warning: 'static' is not at beginning of declaration"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wreturn-type',
        'description': 'Missing return value',
        'patterns': [r".*: warning: control reaches end of non-void function"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wimplicit-int',
        'description':
            'Implicit int type',
        'patterns': [
            r".*: warning: type specifier missing, defaults to 'int'",
            r".*: warning: type defaults to 'int' in declaration of '.+'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wmain-return-type',
        'description': 'Main function should return int',
        'patterns': [r".*: warning: return type of 'main' is not 'int'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wuninitialized',
        'description':
            'Variable may be used uninitialized',
        'patterns': [
            r".*: warning: '.+' may be used uninitialized in this function"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-Wuninitialized',
        'description':
            'Variable is used uninitialized',
        'patterns': [
            r".*: warning: '.+' is used uninitialized in this function",
            r".*: warning: variable '.+' is uninitialized when used here"
        ]
    },
    {
        'category':
            'ld',
        'severity':
            Severity.MEDIUM,
        'option':
            '-fshort-enums',
        'description':
            'ld: possible enum size mismatch',
        'patterns': [
            r".*: warning: .* uses variable-size enums yet the output is to "
            r"use 32-bit enums; use of enum values across objects may fail"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wpointer-sign',
        'description':
            'Pointer targets differ in signedness',
        'patterns': [
            r".*: warning: pointer targets in initialization differ in "
            r"signedness",
            r".*: warning: pointer targets in assignment differ in signedness",
            r".*: warning: pointer targets in return differ in signedness",
            r".*: warning: pointer targets in passing argument [0-9]+ of '.+' "
            r"differ in signedness"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wstrict-overflow',
        'description':
            'Assuming overflow does not occur',
        'patterns': [
            r".*: warning: assuming signed overflow does not occur when "
            r"assuming that .* is always (true|false)"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wempty-body',
        'description':
            'Suggest adding braces around empty body',
        'patterns': [
            r".*: warning: suggest braces around empty body in an 'if' "
            r"statement", r".*: warning: empty body in an if-statement",
            r".*: warning: suggest braces around empty body in an 'else' "
            r"statement", r".*: warning: empty body in an else-statement"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wparentheses',
        'description':
            'Suggest adding parentheses',
        'patterns': [
            r".*: warning: suggest explicit braces to avoid ambiguous 'else'",
            r".*: warning: suggest parentheses around arithmetic in operand "
            r"of '.+'",
            r".*: warning: suggest parentheses around comparison in operand "
            r"of '.+'",
            r".*: warning: logical not is only applied to the left hand "
            r"side of this comparison",
            r".*: warning: using the result of an assignment as a condition "
            r"without parentheses",
            r".*: warning: .+ has lower precedence than .+ be evaluated "
            r"first .+Wparentheses",
            r".*: warning: suggest parentheses around '.+?' .+ '.+?'",
            r".*: warning: suggest parentheses around assignment used as "
            r"truth value"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Static variable used in non-static inline function',
        'patterns': [
            r".*: warning: '.+' is static but used in inline function '.+' "
            r"which is not static"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wimplicit int',
        'description':
            'No type or storage class (will default to int)',
        'patterns': [
            r".*: warning: data definition has no type or storage class"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Null pointer',
        'patterns': [
            r".*: warning: Dereference of null pointer",
            r".*: warning: Called .+ pointer is null",
            r".*: warning: Forming reference to null pointer",
            r".*: warning: Returning null reference",
            r".*: warning: Null pointer passed as an argument to a 'nonnull' "
            r"parameter",
            r".*: warning: .+ results in a null pointer dereference",
            r".*: warning: Access to .+ results in a dereference of a null "
            r"pointer", r".*: warning: Null pointer argument in"
        ]
    },
    {
        'category':
            'cont.',
        'severity':
            Severity.SKIP,
        'description':
            'skip, parameter name (without types) in function declaration',
        'patterns': [
            r".*: warning: parameter names \(without types\) in function "
            r"declaration"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wstrict-aliasing',
        'description':
            'Dereferencing &lt;foo&gt; breaks strict aliasing rules',
        'patterns': [
            r".*: warning: dereferencing .* break strict-aliasing rules"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wpointer-to-int-cast',
        'description':
            'Cast from pointer to integer of different size',
        'patterns': [
            r".*: warning: cast from pointer to integer of different size",
            r".*: warning: initialization makes pointer from integer without "
            r"a cast"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wint-to-pointer-cast',
        'description':
            'Cast to pointer from integer of different size',
        'patterns': [
            r".*: warning: cast to pointer from integer of different size"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Symbol redefined',
        'patterns': [r".*: warning: "
                     ".+"
                     " redefined"]
    },
    {
        'category':
            'cont.',
        'severity':
            Severity.SKIP,
        'description':
            'skip, ... location of the previous definition',
        'patterns': [
            r".*: warning: this is the location of the previous definition"
        ]
    },
    {
        'category':
            'ld',
        'severity':
            Severity.MEDIUM,
        'description':
            'ld: type and size of dynamic symbol are not defined',
        'patterns': [
            r".*: warning: type and size of dynamic symbol `.+' are not "
            r"defined"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Pointer from integer without cast',
        'patterns': [
            r".*: warning: assignment makes pointer from integer without a "
            r"cast"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Pointer from integer without cast',
        'patterns': [
            r".*: warning: passing argument [0-9]+ of '.+' makes pointer from "
            r"integer without a cast"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Integer from pointer without cast',
        'patterns': [
            r".*: warning: assignment makes integer from pointer without a "
            r"cast"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Integer from pointer without cast',
        'patterns': [
            r".*: warning: passing argument [0-9]+ of '.+' makes integer from "
            r"pointer without a cast"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Integer from pointer without cast',
        'patterns': [
            r".*: warning: return makes integer from pointer without a cast"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wunknown-pragmas',
        'description': 'Ignoring pragma',
        'patterns': [r".*: warning: ignoring #pragma .+"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-W#pragma-messages',
        'description': 'Pragma warning messages',
        'patterns': [r".*: warning: .+W#pragma-messages"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wclobbered',
        'description':
            'Variable might be clobbered by longjmp or vfork',
        'patterns': [
            r".*: warning: variable '.+' might be clobbered by 'longjmp' or "
            r"'vfork'"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wclobbered',
        'description':
            'Argument might be clobbered by longjmp or vfork',
        'patterns': [
            r".*: warning: argument '.+' might be clobbered by 'longjmp' or "
            r"'vfork'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wredundant-decls',
        'description': 'Redundant declaration',
        'patterns': [r".*: warning: redundant redeclaration of '.+'"]
    },
    {
        'category': 'cont.',
        'severity': Severity.SKIP,
        'description': 'skip, previous declaration ... was here',
        'patterns': [r".*: warning: previous declaration of '.+' was here"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wswitch-enum',
        'description':
            'Enum value not handled in switch',
        'patterns': [
            r".*: warning: .*enumeration value.* not handled in "
            r"switch.+Wswitch"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wuser-defined-warnings',
        'description': 'User defined warnings',
        'patterns': [r".*: warning: .* \[-Wuser-defined-warnings\]$"]
    },
    {
        'category':
            'aapt',
        'severity':
            Severity.MEDIUM,
        'description':
            'aapt: No default translation',
        'patterns': [
            r".*: warning: string '.+' has no default translation in .*"
        ]
    },
    {
        'category':
            'aapt',
        'severity':
            Severity.MEDIUM,
        'description':
            'aapt: Missing default or required localization',
        'patterns': [
            r".*: warning: \*\*\*\* string '.+' has no default or required "
            r"localization for '.+' in .+"
        ]
    },
    {
        'category':
            'aapt',
        'severity':
            Severity.MEDIUM,
        'description':
            'aapt: String marked untranslatable, but translation exists',
        'patterns': [
            r".*: warning: string '.+' in .* marked untranslatable but exists "
            r"in locale '??_??'"
        ]
    },
    {
        'category': 'aapt',
        'severity': Severity.MEDIUM,
        'description': 'aapt: empty span in string',
        'patterns': [r".*: warning: empty '.+' span found in text '.+"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Taking address of temporary',
        'patterns': [r".*: warning: taking address of temporary"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Taking address of packed member',
        'patterns': [r".*: warning: taking address of packed member"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Possible broken line continuation',
        'patterns': [r".*: warning: backslash and newline separated by space"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wundefined-var-template',
        'description':
            'Undefined variable template',
        'patterns': [
            r".*: warning: instantiation of variable .* no definition is "
            r"available"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wundefined-inline',
        'description': 'Inline function is not defined',
        'patterns': [r".*: warning: inline function '.*' is not defined"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Warray-bounds',
        'description':
            'Array subscript out of bounds',
        'patterns': [
            r".*: warning: array subscript is above array bounds",
            r".*: warning: Array subscript is undefined",
            r".*: warning: array subscript is below array bounds"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Excess elements in initializer',
        'patterns': [r".*: warning: excess elements in .+ initializer"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Decimal constant is unsigned only in ISO C90',
        'patterns': [
            r".*: warning: this decimal constant is unsigned only in ISO C90"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wmain',
        'description': 'main is usually a function',
        'patterns': [r".*: warning: 'main' is usually a function"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Typedef ignored',
        'patterns': [r".*: warning: 'typedef' was ignored in this declaration"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-Waddress',
        'description':
            'Address always evaluates to true',
        'patterns': [
            r".*: warning: the address of '.+' will always evaluate as 'true'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.FIXMENOW,
        'description': 'Freeing a non-heap object',
        'patterns': [r".*: warning: attempt to free a non-heap object '.+'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wchar-subscripts',
        'description':
            'Array subscript has type char',
        'patterns': [
            r".*: warning: array subscript .+ type 'char'.+Wchar-subscripts"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Constant too large for type',
        'patterns': [
            r".*: warning: integer constant is too large for '.+' type"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Woverflow',
        'description':
            'Constant too large for type, truncated',
        'patterns': [
            r".*: warning: large integer implicitly truncated to unsigned type"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Winteger-overflow',
        'description':
            'Overflow in expression',
        'patterns': [
            r".*: warning: overflow in expression; .*Winteger-overflow"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Woverflow',
        'description': 'Overflow in implicit constant conversion',
        'patterns': [r".*: warning: overflow in implicit constant conversion"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Declaration does not declare anything',
        'patterns': [
            r".*: warning: declaration 'class .+' does not declare anything"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wreorder',
        'description':
            'Initialization order will be different',
        'patterns': [
            r".*: warning: '.+' will be initialized after",
            r".*: warning: field .+ will be initialized after .+Wreorder"
        ]
    },
    {
        'category': 'cont.',
        'severity': Severity.SKIP,
        'description': 'skip,   ....',
        'patterns': [r".*: warning:   '.+'"]
    },
    {
        'category': 'cont.',
        'severity': Severity.SKIP,
        'description': 'skip,   base ...',
        'patterns': [r".*: warning:   base '.+'"]
    },
    {
        'category': 'cont.',
        'severity': Severity.SKIP,
        'description': 'skip,   when initialized here',
        'patterns': [r".*: warning:   when initialized here"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wmissing-parameter-type',
        'description': 'Parameter type not specified',
        'patterns': [r".*: warning: type of '.+' defaults to 'int'"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wmissing-declarations',
        'description': 'Missing declarations',
        'patterns': [r".*: warning: declaration does not declare anything"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wmissing-noreturn',
        'description':
            'Missing noreturn',
        'patterns': [
            r".*: warning: function '.*' could be declared with attribute "
            r"'noreturn'"
        ]
    },
    # pylint:disable=anomalous-backslash-in-string
    # TODO(chh): fix the backslash pylint warning.
    {
        'category':
            'gcc',
        'severity':
            Severity.MEDIUM,
        'description':
            'Invalid option for C file',
        'patterns': [
            r".*: warning: command line option "
            ".+"
            " is valid for C\+\+\/ObjC\+\+ but not for C"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'User warning',
        'patterns': [r".*: warning: #warning "
                     ".+"
                     ""]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wvexing-parse',
        'description':
            'Vexing parsing problem',
        'patterns': [
            r".*: warning: empty parentheses interpreted as a function "
            r"declaration"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wextra',
        'description': 'Dereferencing void*',
        'patterns': [r".*: warning: dereferencing 'void \*' pointer"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Comparison of pointer and integer',
        'patterns': [
            r".*: warning: ordered comparison of pointer with integer zero",
            r".*: warning: .*comparison between pointer and integer"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Use of error-prone unary operator',
        'patterns': [
            r".*: warning: use of unary operator that may be intended as "
            r"compound assignment"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wwrite-strings',
        'description':
            'Conversion of string constant to non-const char*',
        'patterns': [
            r".*: warning: deprecated conversion from string constant to '.+'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wstrict-prototypes',
        'description': 'Function declaration isn'
                       't a prototype',
        'patterns': [r".*: warning: function declaration isn't a prototype"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wignored-qualifiers',
        'description':
            'Type qualifiers ignored on function return value',
        'patterns': [
            r".*: warning: type qualifiers ignored on function return type",
            r".*: warning: .+ type qualifier .+ has no effect "
            r".+Wignored-qualifiers"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description':
            '&lt;foo&gt; declared inside parameter list, scope limited to '
            'this definition',
        'patterns': [r".*: warning: '.+' declared inside parameter list"]
    },
    {
        'category':
            'cont.',
        'severity':
            Severity.SKIP,
        'description':
            'skip, its scope is only this ...',
        'patterns': [
            r".*: warning: its scope is only this definition or declaration, "
            r"which is probably not what you want"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '-Wcomment',
        'description': 'Line continuation inside comment',
        'patterns': [r".*: warning: multi-line comment"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '-Wcomment',
        'description': 'Comment inside comment',
        'patterns': [r".*: warning: "
                     ".+"
                     " within comment"]
    },
    # Warning "value stored is never read" could be from clang-tidy or clang
    # static analyzer.
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Value stored is never read',
        'patterns': [
            r".*: warning: Value stored to .+ is never "
            r"read.*clang-analyzer-deadcode.DeadStores"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'description': 'Value stored is never read',
        'patterns': [r".*: warning: Value stored to .+ is never read"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '-Wdeprecated-declarations',
        'description': 'Deprecated declarations',
        'patterns': [r".*: warning: .+ is deprecated.+deprecated-declarations"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'option':
            '-Wdeprecated-register',
        'description':
            'Deprecated register',
        'patterns': [
            r".*: warning: 'register' storage class specifier is deprecated"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'option':
            '-Wpointer-sign',
        'description':
            'Converts between pointers to integer types with different sign',
        'patterns': [
            r".*: warning: .+ converts between pointers to integer types "
            r"with different sign"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.HARMLESS,
        'description': 'Extra tokens after #endif',
        'patterns': [r".*: warning: extra tokens at end of #endif directive"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wenum-compare',
        'description':
            'Comparison between different enums',
        'patterns': [
            r".*: warning: comparison between '.+' and '.+'.+Wenum-compare"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wconversion',
        'description':
            'Conversion may change value',
        'patterns': [
            r".*: warning: converting negative value '.+' to '.+'",
            r".*: warning: conversion to '.+' .+ may (alter|change)"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wconversion-null',
        'description':
            'Converting to non-pointer type from NULL',
        'patterns': [
            r".*: warning: converting to non-pointer type '.+' from NULL"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wsign-conversion',
        'description': 'Implicit sign conversion',
        'patterns': [r".*: warning: implicit conversion changes signedness"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wnull-conversion',
        'description':
            'Converting NULL to non-pointer type',
        'patterns': [
            r".*: warning: implicit conversion of NULL constant to '.+'"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wnon-literal-null-conversion',
        'description':
            'Zero used as null pointer',
        'patterns': [
            r".*: warning: expression .* zero treated as a null pointer "
            r"constant"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Implicit conversion changes value',
        'patterns': [
            r".*: warning: implicit conversion .* changes value from .* to "
            r".*-conversion"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Passing NULL as non-pointer argument',
        'patterns': [
            r".*: warning: passing NULL to non-pointer argument [0-9]+ of '.+'"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wctor-dtor-privacy',
        'description':
            'Class seems unusable because of private ctor/dtor',
        'patterns': [
            r".*: warning: all member functions in class '.+' are private"
        ]
    },
    # skip this next one, because it only points out some RefBase-based classes
    # where having a private destructor is perfectly fine
    {
        'category':
            'C/C++',
        'severity':
            Severity.SKIP,
        'option':
            '-Wctor-dtor-privacy',
        'description':
            'Class seems unusable because of private ctor/dtor',
        'patterns': [
            r".*: warning: 'class .+' only defines a private destructor and "
            r"has no friends"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wctor-dtor-privacy',
        'description':
            'Class seems unusable because of private ctor/dtor',
        'patterns': [
            r".*: warning: 'class .+' only defines private constructors and "
            r"has no friends"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wgnu-static-float-init',
        'description':
            'In-class initializer for static const float/double',
        'patterns': [
            r".*: warning: in-class initializer for static data member of "
            r".+const (float|double)"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wpointer-arith',
        'description':
            'void* used in arithmetic',
        'patterns': [
            r".*: warning: pointer of type 'void \*' used in "
            r"(arithmetic|subtraction)",
            r".*: warning: arithmetic on .+ to void is a GNU "
            r"extension.*Wpointer-arith",
            r".*: warning: wrong type argument to increment"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wsign-promo',
        'description':
            'Overload resolution chose to promote from unsigned or enum to '
            'signed type',
        'patterns': [
            r".*: warning: passing '.+' chooses '.+' over '.+'.*Wsign-promo"
        ]
    },
    {
        'category': 'cont.',
        'severity': Severity.SKIP,
        'description': 'skip,   in call to ...',
        'patterns': [r".*: warning:   in call to '.+'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HIGH,
        'option':
            '-Wextra',
        'description':
            'Base should be explicitly initialized in copy constructor',
        'patterns': [
            r".*: warning: base class '.+' should be explicitly initialized "
            r"in the copy constructor"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'VLA has zero or negative size',
        'patterns': [
            r".*: warning: Declared variable-length array \(VLA\) has .+ size"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Return value from void function',
        'patterns': [
            r".*: warning: 'return' with a value, in function returning void"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': 'multichar',
        'description': 'Multi-character character constant',
        'patterns': [r".*: warning: multi-character character constant"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            'writable-strings',
        'description':
            'Conversion from string literal to char*',
        'patterns': [
            r".*: warning: .+ does not allow conversion from string literal "
            r"to 'char \*'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '-Wextra-semi',
        'description': 'Extra \';\'',
        'patterns': [r".*: warning: extra ';' .+extra-semi"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'description':
            'Useless specifier',
        'patterns': [
            r".*: warning: useless storage class specifier in empty "
            r"declaration"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '-Wduplicate-decl-specifier',
        'description': 'Duplicate declaration specifier',
        'patterns': [r".*: warning: duplicate '.+' declaration specifier"]
    },
    {
        'category': 'logtags',
        'severity': Severity.LOW,
        'description': 'Duplicate logtag',
        'patterns': [r".*: warning: tag \".+\" \(.+\) duplicated in .+"]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'typedef-redefinition',
        'description':
            'Typedef redefinition',
        'patterns': [
            r".*: warning: redefinition of typedef '.+' is a C11 feature"
        ]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'gnu-designator',
        'description':
            'GNU old-style field designator',
        'patterns': [
            r".*: warning: use of GNU old-style field designator extension"
        ]
    },
    {
        'category': 'logtags',
        'severity': Severity.LOW,
        'option': 'missing-field-initializers',
        'description': 'Missing field initializers',
        'patterns': [r".*: warning: missing field '.+' initializer"]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'missing-braces',
        'description':
            'Missing braces',
        'patterns': [
            r".*: warning: suggest braces around initialization of",
            r".*: warning: too many braces around scalar initializer "
            r".+Wmany-braces-around-scalar-init",
            r".*: warning: braces around scalar initializer"
        ]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'sign-compare',
        'description':
            'Comparison of integers of different signs',
        'patterns': [
            r".*: warning: comparison of integers of different "
            r"signs.+sign-compare"
        ]
    },
    {
        'category': 'logtags',
        'severity': Severity.LOW,
        'option': 'dangling-else',
        'description': 'Add braces to avoid dangling else',
        'patterns': [
            r".*: warning: add explicit braces to avoid dangling else"
        ]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'initializer-overrides',
        'description':
            'Initializer overrides prior initialization',
        'patterns': [
            r".*: warning: initializer overrides prior initialization of this "
            r"subobject"
        ]
    },
    {
        'category': 'logtags',
        'severity': Severity.LOW,
        'option': 'self-assign',
        'description': 'Assigning value to self',
        'patterns': [
            r".*: warning: explicitly assigning value of .+ to itself"
        ]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'gnu-variable-sized-type-not-at-end',
        'description':
            'GNU extension, variable sized type not at end',
        'patterns': [
            r".*: warning: field '.+' with variable sized type '.+' not at "
            r"the end of a struct or class"
        ]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'tautological-constant-out-of-range-compare',
        'description':
            'Comparison of constant is always false/true',
        'patterns': [
            r".*: comparison of .+ is always "
            r".+Wtautological-constant-out-of-range-compare"
        ]
    },
    {
        'category': 'logtags',
        'severity': Severity.LOW,
        'option': 'overloaded-virtual',
        'description': 'Hides overloaded virtual function',
        'patterns': [r".*: '.+' hides overloaded virtual function"]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'incompatible-pointer-types',
        'description':
            'Incompatible pointer types',
        'patterns': [
            r".*: warning: incompatible pointer types "
            r".+Wincompatible-pointer-types"
        ]
    },
    {
        'category':
            'logtags',
        'severity':
            Severity.LOW,
        'option':
            'asm-operand-widths',
        'description':
            'ASM value size does not match register size',
        'patterns': [
            r".*: warning: value size does not match register size "
            r"specified by the constraint and modifier"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': 'tautological-compare',
        'description': 'Comparison of self is always false',
        'patterns': [r".*: self-comparison always evaluates to false"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': 'constant-logical-operand',
        'description': 'Logical op with constant operand',
        'patterns': [r".*: use of logical '.+' with constant operand"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'option':
            'literal-suffix',
        'description':
            'Needs a space between literal and string macro',
        'patterns': [
            r".*: warning: invalid suffix on literal.+ requires a space "
            r".+Wliteral-suffix"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '#warnings',
        'description': 'Warnings from #warning',
        'patterns': [r".*: warning: .+-W#warnings"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'option':
            'absolute-value',
        'description':
            'Using float/int absolute value function with int/float argument',
        'patterns': [
            r".*: warning: using .+ absolute value function .+ when argument "
            r"is .+ type .+Wabsolute-value",
            r".*: warning: absolute value function '.+' given .+ which may "
            r"cause truncation .+Wabsolute-value"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'option':
            '-Wc++11-extensions',
        'description':
            'Using C++11 extensions',
        'patterns': [
            r".*: warning: 'auto' type specifier is a C\+\+11 extension"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.LOW,
        'description':
            'Refers to implicitly defined namespace',
        'patterns': [
            r".*: warning: using directive refers to implicitly-defined "
            r"namespace .+"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.LOW,
        'option': '-Winvalid-pp-token',
        'description': 'Invalid pp token',
        'patterns': [r".*: warning: missing .+Winvalid-pp-token"]
    },
    {
        'category':
            'link',
        'severity':
            Severity.LOW,
        'description':
            'need glibc to link',
        'patterns': [
            r".*: warning: .* requires at runtime .* glibc .* for linking"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Operator new returns NULL',
        'patterns': [
            r".*: warning: 'operator new' must not return NULL unless it is "
            r"declared 'throw\(\)' .+"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wnull-arithmetic',
        'description':
            'NULL used in arithmetic',
        'patterns': [
            r".*: warning: NULL used in arithmetic",
            r".*: warning: comparison between NULL and non-pointer"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            'header-guard',
        'description':
            'Misspelled header guard',
        'patterns': [
            r".*: warning: '.+' is used as a header guard .+ followed by .+ "
            r"different macro"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': 'empty-body',
        'description': 'Empty loop body',
        'patterns': [r".*: warning: .+ loop has empty body"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            'enum-conversion',
        'description':
            'Implicit conversion from enumeration type',
        'patterns': [
            r".*: warning: implicit conversion from enumeration type '.+'"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': 'switch',
        'description': 'case value not in enumerated type',
        'patterns': [r".*: warning: case value not in enumerated type '.+'"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Undefined result',
        'patterns': [
            r".*: warning: The result of .+ is undefined",
            r".*: warning: passing an object that .+ has undefined behavior "
            r"\[-Wvarargs\]",
            r".*: warning: 'this' pointer cannot be null in well-defined "
            r"C\+\+ code;",
            r".*: warning: shifting a negative signed value is undefined"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Division by zero',
        'patterns': [r".*: warning: Division by zero"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Use of deprecated method',
        'patterns': [r".*: warning: '.+' is deprecated .+"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Use of garbage or uninitialized value',
        'patterns': [
            r".*: warning: .+ is a garbage value",
            r".*: warning: Function call argument is an uninitialized value",
            r".*: warning: Undefined or garbage value returned to caller",
            r".*: warning: Called .+ pointer is.+uninitialized",
            # note that the below matches a typo in compiler message
            r".*: warning: Called .+ pointer is.+uninitalized",
            r".*: warning: Use of zero-allocated memory",
            r".*: warning: Dereference of undefined pointer value",
            r".*: warning: Passed-by-value .+ contains uninitialized data",
            r".*: warning: Branch condition evaluates to a garbage value",
            r".*: warning: The .+ of .+ is an uninitialized value.",
            r".*: warning: .+ is used uninitialized whenever "
            r".+sometimes-uninitialized",
            r".*: warning: Assigned value is garbage or undefined"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Result of malloc type incompatible with sizeof operand type',
        'patterns': [
            r".*: warning: Result of '.+' is converted to .+ incompatible "
            r"with sizeof operand type"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wsizeof-array-argument',
        'description':
            'Sizeof on array argument',
        'patterns': [
            r".*: warning: sizeof on array function parameter will return"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'option': '-Wsizeof-pointer-memacces',
        'description': 'Bad argument size of memory access functions',
        'patterns': [r".*: warning: .+\[-Wsizeof-pointer-memaccess\]"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Return value not checked',
        'patterns': [r".*: warning: The return value from .+ is not checked"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Possible heap pollution',
        'patterns': [r".*: warning: .*Possible heap pollution from .+ type .+"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Allocation size of 0 byte',
        'patterns': [
            r".*: warning: Call to .+ has an allocation size of 0 byte"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'description':
            'Result of malloc type incompatible with sizeof operand type',
        'patterns': [
            r".*: warning: Result of '.+' is converted to .+ incompatible "
            r"with sizeof operand type"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wfor-loop-analysis',
        'description':
            'Variable used in loop condition not modified in loop body',
        'patterns': [
            r".*: warning: variable '.+' used in loop "
            r"condition.*Wfor-loop-analysis"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.MEDIUM,
        'description': 'Closing a previously closed file',
        'patterns': [r".*: warning: Closing a previously closed file"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wunnamed-type-template-args',
        'description':
            'Unnamed template type argument',
        'patterns': [
            r".*: warning: template argument.+Wunnamed-type-template-args"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.MEDIUM,
        'option':
            '-Wimplicit-fallthrough',
        'description':
            'Unannotated fall-through between switch labels',
        'patterns': [
            r".*: warning: unannotated fall-through between switch "
            r"labels.+Wimplicit-fallthrough"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HARMLESS,
        'description':
            'Discarded qualifier from pointer target type',
        'patterns': [
            r".*: warning: .+ discards '.+' qualifier from pointer target type"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HARMLESS,
        'description':
            'Use snprintf instead of sprintf',
        'patterns': [
            r".*: warning: .*sprintf is often misused; please use snprintf"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.HARMLESS,
        'description': 'Unsupported optimizaton flag',
        'patterns': [r".*: warning: optimization flag '.+' is not supported"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HARMLESS,
        'description':
            'Extra or missing parentheses',
        'patterns': [
            r".*: warning: equality comparison with extraneous parentheses",
            r".*: warning: .+ within .+Wlogical-op-parentheses"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.HARMLESS,
        'option':
            'mismatched-tags',
        'description':
            'Mismatched class vs struct tags',
        'patterns': [
            r".*: warning: '.+' defined as a .+ here but previously declared "
            r"as a .+mismatched-tags",
            r".*: warning: .+ was previously declared as a .+mismatched-tags"
        ]
    },
    {
        'category': 'FindEmulator',
        'severity': Severity.HARMLESS,
        'description': 'FindEmulator: No such file or directory',
        'patterns': [
            r".*: warning: FindEmulator: .* No such file or directory"
        ]
    },
    {
        'category':
            'google_tests',
        'severity':
            Severity.HARMLESS,
        'description':
            'google_tests: unknown installed file',
        'patterns': [
            r".*: warning: .*_tests: Unknown installed file for module"
        ]
    },
    {
        'category': 'make',
        'severity': Severity.HARMLESS,
        'description': 'unusual tags debug eng',
        'patterns': [r".*: warning: .*: unusual tags debug eng"]
    },

    # these next ones are to deal with formatting problems resulting from the
    # log being mixed up by 'make -j'
    {
        'category': 'C/C++',
        'severity': Severity.SKIP,
        'description': 'skip, ,',
        'patterns': [r".*: warning: ,$"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.SKIP,
        'description': 'skip,',
        'patterns': [r".*: warning: $"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.SKIP,
        'description': 'skip, In file included from ...',
        'patterns': [r".*: warning: In file included from .+,"]
    },

    # warnings from clang-tidy
    group_tidy_warn_pattern('android'),
    simple_tidy_warn_pattern('bugprone-argument-comment'),
    simple_tidy_warn_pattern('bugprone-copy-constructor-init'),
    simple_tidy_warn_pattern('bugprone-fold-init-type'),
    simple_tidy_warn_pattern('bugprone-forward-declaration-namespace'),
    simple_tidy_warn_pattern('bugprone-forwarding-reference-overload'),
    simple_tidy_warn_pattern('bugprone-inaccurate-erase'),
    simple_tidy_warn_pattern('bugprone-incorrect-roundings'),
    simple_tidy_warn_pattern('bugprone-integer-division'),
    simple_tidy_warn_pattern('bugprone-lambda-function-name'),
    simple_tidy_warn_pattern('bugprone-macro-parentheses'),
    simple_tidy_warn_pattern('bugprone-misplaced-widening-cast'),
    simple_tidy_warn_pattern('bugprone-move-forwarding-reference'),
    simple_tidy_warn_pattern('bugprone-sizeof-expression'),
    simple_tidy_warn_pattern('bugprone-string-constructor'),
    simple_tidy_warn_pattern('bugprone-string-integer-assignment'),
    simple_tidy_warn_pattern('bugprone-suspicious-enum-usage'),
    simple_tidy_warn_pattern('bugprone-suspicious-missing-comma'),
    simple_tidy_warn_pattern('bugprone-suspicious-string-compare'),
    simple_tidy_warn_pattern('bugprone-suspicious-semicolon'),
    simple_tidy_warn_pattern('bugprone-undefined-memory-manipulation'),
    simple_tidy_warn_pattern('bugprone-unused-raii'),
    simple_tidy_warn_pattern('bugprone-use-after-move'),
    group_tidy_warn_pattern('bugprone'),
    group_tidy_warn_pattern('cert'),
    group_tidy_warn_pattern('clang-diagnostic'),
    group_tidy_warn_pattern('cppcoreguidelines'),
    group_tidy_warn_pattern('llvm'),
    simple_tidy_warn_pattern('google-default-arguments'),
    simple_tidy_warn_pattern('google-runtime-int'),
    simple_tidy_warn_pattern('google-runtime-operator'),
    simple_tidy_warn_pattern('google-runtime-references'),
    group_tidy_warn_pattern('google-build'),
    group_tidy_warn_pattern('google-explicit'),
    group_tidy_warn_pattern('google-redability'),
    group_tidy_warn_pattern('google-global'),
    group_tidy_warn_pattern('google-redability'),
    group_tidy_warn_pattern('google-redability'),
    group_tidy_warn_pattern('google'),
    simple_tidy_warn_pattern('hicpp-explicit-conversions'),
    simple_tidy_warn_pattern('hicpp-function-size'),
    simple_tidy_warn_pattern('hicpp-invalid-access-moved'),
    simple_tidy_warn_pattern('hicpp-member-init'),
    simple_tidy_warn_pattern('hicpp-delete-operators'),
    simple_tidy_warn_pattern('hicpp-special-member-functions'),
    simple_tidy_warn_pattern('hicpp-use-equals-default'),
    simple_tidy_warn_pattern('hicpp-use-equals-delete'),
    simple_tidy_warn_pattern('hicpp-no-assembler'),
    simple_tidy_warn_pattern('hicpp-noexcept-move'),
    simple_tidy_warn_pattern('hicpp-use-override'),
    group_tidy_warn_pattern('hicpp'),
    group_tidy_warn_pattern('modernize'),
    group_tidy_warn_pattern('misc'),
    simple_tidy_warn_pattern('performance-faster-string-find'),
    simple_tidy_warn_pattern('performance-for-range-copy'),
    simple_tidy_warn_pattern('performance-implicit-cast-in-loop'),
    simple_tidy_warn_pattern('performance-inefficient-string-concatenation'),
    simple_tidy_warn_pattern('performance-type-promotion-in-math-fn'),
    simple_tidy_warn_pattern('performance-unnecessary-copy-initialization'),
    simple_tidy_warn_pattern('performance-unnecessary-value-param'),
    group_tidy_warn_pattern('performance'),
    group_tidy_warn_pattern('readability'),

    # warnings from clang-tidy's clang-analyzer checks
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Unreachable code',
        'patterns': [
            r".*: warning: This statement is never executed.*UnreachableCode"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Size of malloc may overflow',
        'patterns': [
            r".*: warning: .* size of .* may overflow .*MallocOverflow"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer Stream pointer might be NULL',
        'patterns': [
            r".*: warning: Stream pointer might be NULL .*unix.Stream"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer Opened file never closed',
        'patterns': [r".*: warning: Opened File never closed.*unix.Stream"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer sozeof() on a pointer type',
        'patterns': [
            r".*: warning: .*calls sizeof.* on a pointer type.*SizeofPtr"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Pointer arithmetic on non-array variables',
        'patterns': [
            r".*: warning: Pointer arithmetic on non-array variables "
            r".*PointerArithm"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description':
            'clang-analyzer Subtraction of pointers of different memory '
            'chunks',
        'patterns': [r".*: warning: Subtraction of two pointers .*PointerSub"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Access out-of-bound array element',
        'patterns': [
            r".*: warning: Access out-of-bound array element .*ArrayBound"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer Out of bound memory access',
        'patterns': [r".*: warning: Out of bound memory access .*ArrayBoundV2"]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Possible lock order reversal',
        'patterns': [
            r".*: warning: .* Possible lock order reversal.*PthreadLock"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer Argument is a pointer to uninitialized value',
        'patterns': [
            r".*: warning: .* argument is a pointer to uninitialized value "
            r".*CallAndMessage"
        ]
    },
    {
        'category':
            'C/C++',
        'severity':
            Severity.ANALYZER,
        'description':
            'clang-analyzer cast to struct',
        'patterns': [
            r".*: warning: Casting a non-structure type to a structure type "
            r".*CastToStruct"
        ]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer call path problems',
        'patterns': [r".*: warning: Call Path : .+"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer excessive padding',
        'patterns': [r".*: warning: Excessive padding in '.*'"]
    },
    {
        'category': 'C/C++',
        'severity': Severity.ANALYZER,
        'description': 'clang-analyzer other',
        'patterns': [r".*: .+\[clang-analyzer-.+\]$", r".*: Call Path : .+$"]
    },

    # catch-all for warnings this script doesn't know about yet
    {
        'category': 'C/C++',
        'severity': Severity.UNKNOWN,
        'description': 'Unclassified/unrecognized warnings',
        'patterns': [r".*: warning: .+"]
    },
]
