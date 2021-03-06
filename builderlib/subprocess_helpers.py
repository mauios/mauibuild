#!/usr/bin/python
# vim: et:ts=4:sw=4
#
# Copyright (C) 2012-2013 Pier Luigi Fiorini <pierluigi.fiorini@gmail.com>
# Copyright (C) 2011 Colin Walters <walters@verbum.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import sys
import subprocess

from .logger import Logger

def _get_env_for_cwd(cwd=None, env=None):
    # This dance is necessary because we want to keep the PWD
    # environment variable up to date.  Not doing so is a recipie
    # for triggering edge conditions in pwd lookup.
    if (cwd is not None) and (env is None or ('PWD' in env)):
        if env is None:
            env_copy = os.environ.copy()
        else:
            env_copy = env.copy()
        if ('PWD' in env_copy) and (not cwd.startswith('/')):
            env_copy['PWD'] = os.path.join(env_copy['PWD'], cwd)
        else:
            env_copy['PWD'] = cwd
    else:
        env_copy = env
    return env_copy

def run_sync_get_output(args, cwd=None, env=None, stdout=None, stderr=None, none_on_error=False,
                        log_success=False, log_initiation=False):
    logger = Logger()

    if log_initiation:
        logger.info("Running: %s" % (subprocess.list2cmdline(args),))

    env_copy = _get_env_for_cwd(cwd, env)

    f = open('/dev/null', 'r')

    if stderr is None:
        stderr_target = sys.stderr
    else:
        stderr_target = stderr
    proc = subprocess.Popen(args, stdin=f, stdout=subprocess.PIPE, stderr=stderr_target,
                            close_fds=True, cwd=cwd, env=env_copy)
    f.close()
    output = proc.communicate()[0].strip()
    if proc.returncode != 0 and not none_on_error:
        logfn = logger.fatal
    elif log_success:
        logfn = logger.debug
    else:
        logfn = None
    if logfn is not None:
        logfn("cmd '%s' (cwd=%s) exited with code %d, %d bytes of output" % (subprocess.list2cmdline(args),
                                                                             cwd, proc.returncode, len(output)))
    if proc.returncode == 0:
        return output
    return None

def run_sync_with_input_get_output(args, input, cwd=None, env=None, stderr=None,
                                   none_on_error=False, log_success=False, log_initiation=False):
    logger = Logger()

    if log_initiation:
        logger.info("Running: %s" % (subprocess.list2cmdline(args),))

    env_copy = _get_env_for_cwd(cwd, env)

    if stderr is None:
        stderr_target = sys.stderr
    else:
        stderr_target = stderr

    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr_target,
                            close_fds=True, cwd=cwd, env=env_copy)
    output = proc.communicate(input=input)[0].strip()
    if proc.returncode != 0 and not none_on_error:
        logfn = logger.fatal
    elif log_success:
        logfn = logger.debug
    else:
        logfn = None
    if logfn is not None:
        logfn("cmd '%s' (cwd=%s) exited with code %d, %d bytes of output" % (subprocess.list2cmdline(args),
                                                                             cwd, proc.returncode, len(output)))
    if proc.returncode == 0:
        return output
    return None

def run_async(args, cwd=None, env=None, log_initiation=True, stdout=None,
              stderr=None):
    logger = Logger()

    if log_initiation:
        logger.info("Running: %s" % (subprocess.list2cmdline(args),))

    env_copy = _get_env_for_cwd(cwd, env)

    if stdout is None:
        stdout_target = sys.stdout
    else:
        stdout_target = stdout

    if stderr is None:
        stderr_target = sys.stderr
    else:
        stderr_target = stderr

    proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                            stdout=stdout_target, stderr=stderr_target,
                            close_fds=True, cwd=cwd, env=env_copy)
    return proc

def run_sync(args, cwd=None, env=None, fatal_on_error=True, keep_stdin=False,
             log_success=True, log_initiation=True, stdin=None, stdout=None,
             stderr=None, return_exitcode=False):
    logger = Logger()

    if log_initiation:
        logger.info("Running: %s" % (subprocess.list2cmdline(args),))

    env_copy = _get_env_for_cwd(cwd, env)

    if stdin is not None:
        stdin_target = stdin
    elif keep_stdin:
        stdin_target = sys.stdin
    else:
        stdin_target = open('/dev/null', 'r')

    if stdout is None:
        stdout_target = sys.stdout
    else:
        stdout_target = stdout

    if stderr is None:
        stderr_target = sys.stderr
    else:
        stderr_target = stderr

    proc = subprocess.Popen(args, stdin=stdin_target, stdout=stdout_target, stderr=stderr_target,
                            close_fds=True, cwd=cwd, env=env_copy)
    if not keep_stdin:
        stdin_target.close()
    returncode = proc.wait()
    if fatal_on_error and returncode != 0:
        logfn = logger.fatal
    elif log_success:
        logfn = logger.debug
    else:
        logfn = None
    if logfn is not None:
        if not log_initiation:
            logfn("Command %s exited with code %d" % (subprocess.list2cmdline(args), returncode))
        else:
            logfn("pid %d exited with code %d" % (proc.pid, returncode))
    success = os.WIFEXITED(returncode) and os.WEXITSTATUS(returncode) == 0
    if return_exitcode:
        return (success, returncode)
    return success
