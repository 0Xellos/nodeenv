#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    nve
    ~~~
    nve - Node.js virtual environment

    TODO:
        - local installation (without setup.py, package install)
        - add option --debug for compile
        - add option --profile for compile
        - add quete
        - save command line at creation
        - save/load installed package state (freeze)
        - add setup.py

    :copyright: (c) 2011 by Eugene Kalinin
    :license: BSD, see LICENSE for more details.
"""

nve_version = '0.2'

import sys
import os
import subprocess
import optparse
import logging

join = os.path.join
abspath = os.path.abspath

# ---------------------------------------------------------
# Utils

def create_logger():
    """
    Create logger for diagnostic
    """
    # create logger
    logger = logging.getLogger("node-venv")
    logger.setLevel(logging.DEBUG)

    # monkey patch
    def emit(self, record):
        msg = self.format(record)
        fs = "%s" if getattr(record, "continued", False) else "%s\n"
        self.stream.write(fs % msg)
        self.flush()
    logging.StreamHandler.emit = emit

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter(fmt="%(message)s")

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)
    return logger 
logger = create_logger()


def parse_args():
    """
    Parses command line arguments
    """
    parser = optparse.OptionParser(
        version=nve_version,
        usage="%prog [OPTIONS] DEST_DIR")

    parser.add_option('-n', '--node', dest='node', 
        metavar='NODE_VER', default=get_last_stable_node_version(),
        help='The node.js version to use, e.g., '
        '--node=0.4.3 will use the node-v0.4.3 '
        'to create the new environment. The default is last stable version.')

    parser.add_option('-v', '--verbose',
        action='store_true', dest='verbose', default=False,
        help="Verbose mode")

    parser.add_option('--prompt', dest='prompt',
        help='Provides an alternative prompt prefix for this environment')

    parser.add_option('-l', '--list', dest='list',
        action='store_true', default=False,
        help='Lists available node.js versions')

    parser.add_option( '--without-ssl', dest='without_ssl',
        action='store_true', default=False, 
        help='Build node.js without SSL support')

    parser.add_option( '--without-npm', dest='without_npm',
        action='store_true', default=False, 
        help='Install npm in new virtual environment')

    options, args = parser.parse_args()

    if not options.list:
        if not args:
            print('You must provide a DEST_DIR')
            parser.print_help()
            sys.exit(2)

        if len(args) > 1:
            print('There must be only one argument: DEST_DIR (you gave %s)' % (
                ' '.join(args)))
            parser.print_help()
            sys.exit(2)

    return options, args


def mkdir(path):
    """
    Create directory
    """
    if not os.path.exists(path):
        logger.info(' * Creating: %s ... ', path, extra=dict(continued=True))
        os.makedirs(path)
        logger.info('done.')
    else:
        logger.info(' * Directory %s already exists', path)


def writefile(dest, content, overwrite=True):
    if not os.path.exists(dest):
        logger.info(' * Writing %s ... ', dest, extra=dict(continued=True))
        f = open(dest, 'wb')
        f.write(content.encode('utf-8'))
        f.close()
        logger.info('done.')
        return
    else:
        f = open(dest, 'rb')
        c = f.read()
        f.close()
        if c != content:
            if not overwrite:
                logger.notify(' * File %s exists with different content; not overwriting', dest)
                return
            logger.notify(' * Overwriting %s with new content', dest)
            f = open(dest, 'wb')
            f.write(content.encode('utf-8'))
            f.close()
        else:
            logger.info(' * Content %s already in place', dest)


def callit(cmd, show_stdout=True, cwd=None):
    """
    Execute cmd
    """
    if show_stdout:
        stdout = None
    else:
        stdout = subprocess.PIPE
    logger.debug(" * Running command %s", cmd)
    try:
        proc = subprocess.Popen(cmd, stderr=subprocess.STDOUT,
            stdin=None, stdout=stdout, cwd=cwd)
    except Exception:
        e = sys.exc_info()[1]
        logger.fatal("Error %s while executing command %s"%(e, cmd))
        raise


# ---------------------------------------------------------
# Virtual environment functions

def install_node(env_dir, src_dir, opt):
    """
    Download source code for node.js, unpack it
    and install it in virtual environment.
    """
    node_name = 'node-v%s'%(opt.node)
    tar_name = '%s.tar.gz'%(node_name)
    node_url = 'http://nodejs.org/dist/%s'%(tar_name)
    node_tar = join(src_dir, tar_name)
    node_src_dir = join(src_dir, node_name)
    env_dir = abspath(env_dir)
    old_chdir = os.getcwd()

    if not os.path.exists(node_src_dir):
        logger.info(' * Retrieve: %s ... ', node_url)
        os.system('curl -# -L "%s" | tar xzf - -C "%s" '%
            (node_url, src_dir))
        logger.info(' * Retrieve: %s ... done.', node_url)
    else:
        logger.info(' * Source exists: %s'%(node_src_dir))

    conf_cmd = './configure --prefix=%s'%(env_dir)
    if opt.without_ssl:
        conf_cmd += ' --without-ssl'
    try:
        os.chdir(node_src_dir)
        if opt.verbose:
            logger.info(' * Compile: %s ...', node_src_dir)
            os.system(conf_cmd)
            os.system('make')
            os.system('make install')
            logger.info(' * Compile: %s ... done', node_src_dir)
        else:
            logger.info(' * Compile: %s ... ', node_src_dir, extra=dict(continued=True))
            c = subprocess.Popen(conf_cmd, shell=True, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c.communicate()
            m = subprocess.Popen('make', shell=True, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            m.communicate()
            mi= subprocess.Popen('make install', shell=True, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            mi.communicate()
            logger.info('done.')
    finally:
        if os.getcwd() != old_chdir:
            os.chdir(old_chdir)


def install_npm(env_dir, src_dir, opt):
    """
    Download source code for npm, unpack it
    and install it in virtual environment.
    """
    if opt.verbose:
        logger.info(' * Install node.js package manager ... ')
        os.system('. %s && curl %s|bash && deactivate'%(
                join(env_dir, 'bin', 'activate'), 
                'http://npmjs.org/install.sh'))
        logger.info(' * Install node.js package manager ... done.')
    else:
        logger.info(' * Install node.js package manager ... ', 
            extra=dict(continued=True))
        npm = subprocess.Popen('. %s && curl %s|bash && deactivate'%(
                join(env_dir, 'bin', 'activate'), 
                'http://npmjs.org/install.sh'), shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        npm.communicate()
        logger.info('done.')


def install_activate(env_dir, opt):
    """
    Install virtual environment activation script
    """
    files = {'activate': ACTIVATE_SH}
    bin_dir = join(env_dir, 'bin')
    prompt = opt.prompt or '(env-%s)'%opt.node 
    for name, content in files.items():
        file_path = join(bin_dir, name)
        content = content.replace('__VIRTUAL_PROMPT__', prompt)
        content = content.replace('__VIRTUAL_ENV__', os.path.abspath(env_dir))
        content = content.replace('__BIN_NAME__', os.path.basename(bin_dir))
        writefile(file_path, content)
        os.chmod(file_path, 0755)


def create_environment(env_dir, opt):
    """
    Creates a new environment in ``env_dir``.
    """
    if os.path.exists(env_dir):
        logger.info(' * Environment is allready exists: %s', env_dir)
        sys.exit(2)
    src_dir = abspath(join(env_dir, 'src'))
    mkdir(src_dir)

    install_node(env_dir, src_dir, opt)
    # activate script install must be
    # before npm install, npm use activate
    # for install
    install_activate(env_dir, opt)
    if not opt.without_npm:
        install_npm(env_dir, src_dir, opt)


def print_node_versions():
    """
    Prints into stdout all available node.js versions
    """
    p = subprocess.Popen(
        "curl -s http://nodejs.org/dist/ | "
        "egrep -o '[0-9]+\.[0-9]+\.[0-9]+' | "
        "sort -u -k 1,1n -k 2,2n -k 3,3n -t . ",
        shell=True, stdout=subprocess.PIPE)
    #out, err = p.communicate()
    pos = 0
    rowx = []
    while 1:
        row = p.stdout.readline()
        pos += 1
        if not row:
            logger.info('\t'.join(rowx))
            break
        if pos%8 == 0:
            logger.info('\t'.join(rowx))
            rowx =[]
        else:
            rowx.append(row.replace('\n', ''))


def get_last_stable_node_version():
    """
    Return last stable node.js version
    """
    p = subprocess.Popen(
        "curl -s http://nodejs.org/dist/ | "
        "egrep -o '[0-9]+\.[2468]+\.[0-9]+' | "
        "sort -u -k 1,1n -k 2,2n -k 3,3n -t . | "
        "tail -n1",
        shell=True, stdout=subprocess.PIPE)
    return p.stdout.readline().replace("\n", "")


def main():
    opt, args = parse_args()
    if opt.list:
        print_node_versions()
    else:
        env_dir = args[0]
        create_environment(env_dir, opt)


# ---------------------------------------------------------
# Shell scripts content

ACTIVATE_SH = """
# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly

deactivate () {
    # reset old environment variables
    if [ -n "$_OLD_VIRTUAL_PATH" ] ; then
        PATH="$_OLD_VIRTUAL_PATH"
        export PATH
        unset _OLD_VIRTUAL_PATH
    fi
    if [ -n "$_OLD_VIRTUAL_PYTHONHOME" ] ; then
        PYTHONHOME="$_OLD_VIRTUAL_PYTHONHOME"
        export PYTHONHOME
        unset _OLD_VIRTUAL_PYTHONHOME
    fi

    # This should detect bash and zsh, which have a hash command that must
    # be called to get it to forget past commands.  Without forgetting
    # past commands the $PATH changes we made may not be respected
    if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
        hash -r
    fi

    if [ -n "$_OLD_VIRTUAL_PS1" ] ; then
        PS1="$_OLD_VIRTUAL_PS1"
        export PS1
        unset _OLD_VIRTUAL_PS1
    fi

    unset VIRTUAL_ENV
    if [ ! "$1" = "nondestructive" ] ; then
    # Self destruct!
        unset -f deactivate
    fi
}

# unset irrelavent variables
deactivate nondestructive

VIRTUAL_ENV="__VIRTUAL_ENV__"
export VIRTUAL_ENV

_OLD_VIRTUAL_PATH="$PATH"
PATH="$VIRTUAL_ENV/__BIN_NAME__:$PATH"
export PATH

if [ -z "$VIRTUAL_ENV_DISABLE_PROMPT" ] ; then
    _OLD_VIRTUAL_PS1="$PS1"
    if [ "x__VIRTUAL_PROMPT__" != x ] ; then
    PS1="__VIRTUAL_PROMPT__$PS1"
    else
    if [ "`basename \"$VIRTUAL_ENV\"`" = "__" ] ; then
        # special case for Aspen magic directories
        # see http://www.zetadev.com/software/aspen/
        PS1="[`basename \`dirname \"$VIRTUAL_ENV\"\``] $PS1"
    else
        PS1="(`basename \"$VIRTUAL_ENV\"`)$PS1"
    fi
    fi
    export PS1
fi

# This should detect bash and zsh, which have a hash command that must
# be called to get it to forget past commands.  Without forgetting
# past commands the $PATH changes we made may not be respected
if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
    hash -r
fi
"""

if __name__ == '__main__':
    main()

