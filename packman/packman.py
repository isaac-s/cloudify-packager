#!/usr/bin/env python
########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import logging
import logging.config

import config
import definitions as defs
import packages

import os
from fabric.api import *  # NOQA
import sys
import re
from time import sleep
from jinja2 import Environment, FileSystemLoader

# __all__ = ['list']


def init_logger(base_level=logging.INFO, verbose_level=logging.DEBUG):
    """
    initialize a logger to be used throughout packman.

    you can use this to init a logger in any of your files.
    this will use config.py's LOGGER param and dictConfig to configure
    the logger for you.

    :param int|logging.LEVEL base_level: desired base logging level
    :param int|logging.LEVEL verbose_level: desired verbose logging level
    :rtype: `python logger`
    """
    log_dir = os.path.dirname(config.LOGGER['handlers']['file']['filename'])
    if os.path.isfile(log_dir):
        sys.exit('file {0} exists - log directory cannot be created '
                 'there. please remove the file and try again.'
                 .format(log_dir))
    try:
        logfile = config.LOGGER['handlers']['file']['filename']
        d = os.path.dirname(logfile)
        if not os.path.exists(d):
            os.makedirs(d)
        logging.config.dictConfig(config.LOGGER)
        lgr = logging.getLogger('user')
        lgr.setLevel(base_level) if not config.VERBOSE \
            else lgr.setLevel(verbose_level)
        return lgr
    except ValueError:
        sys.exit('could not initialize logger.'
                 ' verify your logger config'
                 ' and permissions to write to {0}'
                 .format(logfile))

lgr = init_logger()


def _todo(type, task, todo_file='TODO.md', doc_file='todo.rst'):
    """
    writes to todo files
    """

    with open('../' + todo_file, 'w') as f:
        f.write(type + ': ' + task)
    # with open('../docs/' + doc_file, '+a') as f:
    #     f.write(type + ': ' + task)


def _handle(func):
    """
    handles errors triggered by fabric
    """
    def execution_handler(*args, **kwargs):
        response = func(*args, **kwargs)
        return True and lgr.debug('successfully ran command!') \
            if response.succeeded \
            else False and lgr.error('failed - {0} ({1})'.format(
                response.stderr, response.return_code))
    return execution_handler


def get_package_configuration(component):
    """
    retrieves a package's configuration from packages.PACKAGES

    :param string component: component name to retrieve config for.
    :rtype: `dict` representing package configuration
    """
    lgr.debug('retrieving configuration for {0}'.format(component))
    try:
        package_config = packages.PACKAGES[component]
        lgr.debug('{0} config retrieved successfully'.format(component))
        return package_config
    except KeyError:
        lgr.error('package configuration for'
                  ' {0} was not found, terminating...'.format(component))
        sys.exit(1)


def get(component):
    """
    retrieves resources for packaging

    .. note:: component params are defined in packages.py

    .. note:: param names in packages.py can be overriden by editing
     definitions.py

    :param dict package: dict representing package config
     as configured in packages.py
    :param string name: package's name
     will be appended to the filename and to the package
     depending on its type
    :param string version: version to append to package
    :param string source_url: source url to download
    :param string source_repo: source repo to add for package retrieval
    :param string source_ppa: source ppa to add for package retrieval
    :param string source_key: source key to download
    :param string key_file: key file path
    :param list reqs: list of apt requirements
    :param string dst_path: path where downloaded source are placed
    :param string package_path: path where final package is placed
    :param list modules: list of python modules to download
    :param list gems: list of ruby gems to download
    :param bool overwrite: indicated whether the sources directory be
     erased before creating a new package
    :rtype: `None`
    """

    c = get_package_configuration(component)
    # define params for packaging
    auto_get = c[defs.PARAM_AUTO_GET] \
        if defs.PARAM_AUTO_GET in c else True
    if auto_get:
        source_repo = c[defs.PARAM_SOURCE_REPO] \
            if defs.PARAM_SOURCE_REPO in c else False
        source_ppa = c[defs.PARAM_SOURCE_PPA] \
            if defs.PARAM_SOURCE_PPA in c else False
        source_key = c[defs.PARAM_SOURCE_KEY] \
            if defs.PARAM_SOURCE_KEY in c else False
        source_urls = c[defs.PARAM_SOURCE_URL] \
            if defs.PARAM_SOURCE_URLS in c else False
        key_file = c[defs.PARAM_KEY_FILE_PATH] \
            if defs.PARAM_KEY_FILE_PATH in c else False
        reqs = c[defs.PARAM_REQS] \
            if defs.PARAM_REQS in c else False
        dst_path = c[defs.PARAM_SOURCES_PATH] \
            if defs.PARAM_SOURCES_PATH in c else False
        package_path = c[defs.PARAM_PACKAGE_PATH] \
            if defs.PARAM_PACKAGE_PATH in c else False
        modules = c[defs.PARAM_MODULES] \
            if defs.PARAM_MODULES in c else False
        gems = pakcage[defs.PARAM_GEMS] \
            if defs.PARAM_GEMS in c else False
        overwrite = c[defs.PARAM_OVERWRITE_SOURCES] \
            if defs.PARAM_OVERWRITE_SOURCES in c else True

        common = CommonHandler()
        apt_handler = AptHandler()
        dl_handler = DownloadsHandler()
        py_handler = PythonHandler()
        ruby_handler = RubyHandler()
        # should the source dir be removed before retrieving package contents?
        if overwrite:
            lgr.info('overwrite enabled. removing directory before retrieval')
            common.rmdir(dst_path)
        else:
            if os.path.isdir(dst_path):
                lgr.error('the destination directory for this package already '
                          'exists and overwrite is disabled.')
        # create the directories required for package creation...
        # TODO: remove make_package_paths and create the relevant dirs manually
        common.mkdir(package_path + '/archives')
        common.mkdir(dst_path)
        # if there's a source repo to add... add it.
        # TODO: SEND LIST OF REPOS WITh MARKS
        if source_repo:
            apt_handler.add_src_repo(source_repo, 'deb')
        # if there's a source ppa to add... add it?
        if source_ppa:
            apt_handler.add_ppa_repo(source_ppa)
        # get a key for the repo if it's required..
        if source_key:
            dl_handler.wget(source_key, dst_path)
        # retrieve the source for the package
        if source_urls:
            for url in source_urls:
                dl_handler.wget(url, dst_path)
        # add the repo key
        if key_file:
            apt_handler.add_key(key_file)
            apt_handler.apt_update()
        # apt download any other requirements if they exist
        if reqs:
            apt_handler.apt_download_reqs(reqs, dst_path)
        # download relevant python modules...
        if modules:
            for module in modules:
                py_handler.get_python_module(module, dst_path)
        # download relevant ruby gems...
        if gems:
            for gem in gems:
                ruby_handler.get_ruby_gem(gem, dst_path)
    else:
        lgr.info('component is set to manual retrieval')


def pack(component):
    """
    creates a package according to the provided package configuration
    in packages.py
    uses fpm (https://github.com/jordansissel/fpm/wiki) to create packages.

    .. note:: component params are defined in packages.py

    .. note:: param names in packages.py can be overriden by editing
     definitions.py

    :param string component: string representing component name
     as configured in packages.py
    :param string name: package's name
     will be appended to the filename and to the package
     depending on its type
    :param string version: version to append to package
    :param string src_pkg_type: package source type (as supported by fpm)
    :param string dst_pkg_type: package destination type (as supported by fpm)
    :param string src_path: path containing sources
     from which package will be created
    :param string tmp_pkg_path: path where temp package is placed
    :param string package_path: path where final package is placed
    :param string bootstrap_script: path to place generated script
    :param string bootstrap_script_in_pkg:
    :param dict config_templates: configuration dict for the package's
     config files
    :param bool overwrite: indicated whether the destination directory be
     erased before creating a new package
    :rtype: `None`
    """

    # get the cwd since fpm will later change it.
    cwd = os.getcwd()

    c = get_package_configuration(component)
    # define params for packaging
    auto_pack = c[defs.PARAM_AUTO_PACK] \
        if defs.PARAM_AUTO_PACK in c else True
    if auto_pack:
        name = c[defs.PARAM_NAME] \
            if defs.PARAM_NAME in c else False
        version = c[defs.PARAM_VERSION] \
            if defs.PARAM_VERSION in c else False
        bootstrap_template = c[defs.PARAM_BOOTSTRAP_TEMPLATE_PATH] \
            if defs.PARAM_BOOTSTRAP_TEMPLATE_PATH in c else False
        bootstrap_script = c[defs.PARAM_BOOTSTRAP_SCRIPT_PATH] \
            if defs.PARAM_BOOTSTRAP_SCRIPT_PATH in c else False
        bootstrap_script_in_pkg = cwd + '/' + \
            c[defs.PARAM_BOOTSTRAP_SCRIPT_IN_PACKAGE_PATH] \
            if defs.PARAM_BOOTSTRAP_SCRIPT_IN_PACKAGE_PATH in c else False
        src_pkg_type = c[defs.PARAM_SOURCE_PACKAGE_TYPE] \
            if defs.PARAM_SOURCE_PACKAGE_TYPE in c else False
        dst_pkg_type = c[defs.PARAM_DESTINATION_PACKAGE_TYPE] \
            if defs.PARAM_DESTINATION_PACKAGE_TYPE in c else False
        sources_path = c[defs.PARAM_SOURCES_PATH] \
            if defs.PARAM_SOURCES_PATH in c else False
        # TODO: JEEZ... this archives thing is dumb...
        # replace it with a normal destination path
        tmp_pkg_path = '{0}/archives'.format(c[defs.PARAM_SOURCES_PATH]) \
            if defs.PARAM_SOURCES_PATH else False
        package_path = c[defs.PARAM_PACKAGE_PATH] \
            if defs.PARAM_PACKAGE_PATH in c else False
        depends = c[defs.PARAM_DEPENDS] \
            if defs.PARAM_DEPENDS in c else False
        config_templates = c[defs.PARAM_CONFIG_TEMPLATE_CONFIG] \
            if defs.PARAM_CONFIG_TEMPLATE_CONFIG in c else False
        overwrite = c[defs.PARAM_OVERWRITE_OUTPUT_PACKAGE] \
            if defs.PARAM_OVERWRITE_OUTPUT_PACKAGE in c else True

        common = CommonHandler()
        tmp_handler = TemplateHandler()

        # can't use sources_path == tmp_pkg_path for the package... duh!
        if sources_path == tmp_pkg_path:
            lgr.error('source and destination paths must'
                      ' be different to avoid conflicts!')
        lgr.info('cleaning up before packaging...')

        # should the packaging process overwrite the previous packages?
        if overwrite:
            lgr.info('overwrite enabled. removing directory before packaging')
            common.rm('{0}/{1}*'.format(package_path, name))
        # if the package is ...
        if src_pkg_type:
            common.rmdir(tmp_pkg_path)
            common.mkdir(tmp_pkg_path)

        lgr.info('generating package scripts and config files...')
        # if there are configuration templates to generate configs from...
        if config_templates:
            tmp_handler.generate_configs(c)
        # if bootstrap scripts are required, generate them.
        if bootstrap_script or bootstrap_script_in_pkg:
            # TODO: handle cases where a bootstrap script is not a template.
            # bootstrap_script - bootstrap script to be attached to the package
            # bootstrap_script_in_pkg - same but for putting inside the package
            if bootstrap_template and bootstrap_script:
                tmp_handler.create_bootstrap_script(c, bootstrap_template,
                                                    bootstrap_script)
            if bootstrap_template and bootstrap_script_in_pkg:
                tmp_handler.create_bootstrap_script(c, bootstrap_template,
                                                    bootstrap_script_in_pkg)
                # if it's in_pkg, grant it exec permissions and copy it to the
                # package's path.
                if bootstrap_script_in_pkg:
                    lgr.debug('granting execution permissions')
                    do('chmod +x {0}'.format(bootstrap_script_in_pkg))
                    lgr.debug('copying bootstrap script to package directory')
                    common.cp(bootstrap_script_in_pkg, sources_path)
        lgr.info('packing up component...')
        # if a package needs to be created (not just files copied)...
        if src_pkg_type:
            lgr.info('packing {0}'.format(name))
            # if the source dir for the package exists
            if common.is_dir(sources_path):
                # change the path to the destination path, since fpm doesn't
                # accept (for now) a dst dir, but rather creates the package in
                # the cwd.
                with lcd(tmp_pkg_path):
                    # these will handle the different packages cases based on
                    # the requirement. for instance, if a bootstrap script
                    # exists, and there are dependencies for the package, run
                    # fpm with the relevant flags.
                    if bootstrap_script_in_pkg and dst_pkg_type == "tar":
                        do(
                            'sudo fpm -s {0} -t {1} -n {2} -v {3} -f {4}'
                            .format(src_pkg_type, "tar", name, version,
                                    sources_path))
                    elif bootstrap_script and not depends:
                        do(
                            'sudo fpm -s {0} -t {1} --after-install {2} -n {3}'
                            ' -v {4} -f {5}'
                            .format(src_pkg_type, dst_pkg_type, os.getcwd() +
                                    '/' + bootstrap_script, name, version,
                                    sources_path))
                    elif bootstrap_script and depends:
                        lgr.debug('package dependencies are: {0}'.format(", "
                                  .join(depends)))
                        dep_str = "-d " + " -d ".join(depends)
                        do(
                            'sudo fpm -s {0} -t {1} --after-install {2} {3} -n'
                            ' {4} -v {5} -f {6}'
                            .format(src_pkg_type, dst_pkg_type, os.getcwd() +
                                    '/' + bootstrap_script, dep_str,
                                    name, version, sources_path))
                    # else just create a package with default flags...
                    else:
                        if dst_pkg_type.startswith("tar"):
                            do(
                                'sudo fpm -s {0} -t {1} -n {2} -v {3} -f {4}'
                                .format(src_pkg_type, "tar", name, version,
                                        sources_path))
                        else:
                            do(
                                'sudo fpm -s {0} -t {1} -n {2} -v {3} -f {4}'
                                .format(src_pkg_type, dst_pkg_type, name,
                                        version, sources_path))
                        if dst_pkg_type == "tar.gz":
                            do('sudo gzip {0}*'.format(name))
                    # and check if the packaging process succeeded.
                    # TODO: actually test the package itself.
            # apparently, the src for creation the package doesn't exist...
            # what can you do?
            else:
                lgr.error('sources dir {0} does\'nt exist, termintating...'
                          .format(sources_path))
                # maybe bluntly exit since this is all irrelevant??
                sys.exit(1)

        # make sure the final destination for the package exists..
        if not common.is_dir(package_path):
            common.mkdir(package_path)
        lgr.info("isolating archives...")
        # and then copy the final package over..
        common.cp('{0}/*.{1}'.format(tmp_pkg_path, dst_pkg_type), package_path)
        lgr.info('package creation completed successfully!')
        # TODO: remove temporary package
    else:
        lgr.info('package is set to be packaged manually')


def do(command, retries=2, sleeper=3,
       capture=False, combine_stderr=False):
    """
    executes a command locally with retries on failure.

    :param string command: shell command to be executed
    :param int retries: number of retries to perform on failure
    :param int sleeper: sleeptime between retries
    :param bool capture: should the output be captured for parsing?
    :param bool combine_stderr: combine stdout and stderr
    :rtype: `responseObject` (for fabric operation)
    """
    def _execute():
        for execution in xrange(retries):
            with settings(warn_only=True):
                x = local('sudo {0}'.format(command), capture) if sudo \
                    else local(command, capture)
                if x.succeeded:
                    lgr.debug('successfully executed: ' + command)
                    return x
                lgr.warning('failed to run command: {0} -retrying ({1}/{2})'
                            .format(command, execution + 1, retries))
                sleep(sleeper)
        lgr.error('failed to run command: {0} even after {1} retries'
                  ' with output: {2}'
                  .format(command, execution, x.stdout))
        return x

    # lgr.info('running command: {0}'.format(command))
    if config.VERBOSE:
        return _execute()
    else:
        with hide('running'):
            return _execute()


class CommonHandler():
    """
    common class to handle files and directories
    """
    def find_in_dir(self, dir, pattern):
        """
        finds a string/file pattern in a dir

        :param string dir: directory to look in
        :param string patten: what to look for
        :rtype: ``stdout`` `string` if found, else `None`
        """
        lgr.debug('looking for {0} in {1}'.format(pattern, dir))
        x = do('find {0} -iname "{1}" -exec echo {} \;'
               .format(dir, pattern), capture=True)
        return x.stdout if x.succeeded else None

    def is_dir(self, dir):
        """
        checks if a directory exists

        :param string dir: directory to check
        :rtype: `bool`
        """
        lgr.debug('checking if {0} exists'.format(dir))
        if os.path.isdir(dir):
            lgr.debug('{0} exists'.format(dir))
            return True
        else:
            lgr.debug('{0} does not exist'.format(dir))
            return False

    def is_file(self, file):
        """
        checks if a file exists

        :param string file: file to check
        :rtype: `bool`
        """
        lgr.debug('checking if {0} exists'.format(file))
        if os.path.isfile(file):
            lgr.debug('{0} exists'.format(file))
            return True
        else:
            lgr.debug('{0} does not exist'.format(file))
            return False

    def mkdir(self, dir):
        """
        creates (recursively) a directory

        :param string dir: directory to create
        """
        lgr.debug('creating directory {0}'.format(dir))
        return do('sudo mkdir -p {0}'.format(dir)) if not os.path.isdir(dir) \
            else lgr.debug('directory already exists, skipping.')

    def rmdir(self, dir):
        """
        deletes a directory

        :param string dir: directory to remove
        """
        lgr.debug('attempting to remove directory {0}'.format(dir))
        return do('sudo rm -rf {0}'.format(dir)) \
            if os.path.isdir(dir) else lgr.warning('dir doesn\'t exist')

    def rm(self, file):
        """
        deletes a file or a set of files

        :param string file(s): file(s) to remove
        """
        lgr.info('removing files {0}'.format(file))
        return do('sudo rm {0}'.format(file))
        # if os.path.exists(file) \
        # else lgr.warning('file(s) do(es)n\'t exist')

    def cp(self, src, dst, recurse=True):
        """
        copies (recuresively or not) files or directories

        :param string src: source to copy
        :param string dst: destination to copy to
        :param bool recurse: should the copying process be recursive?
        """
        lgr.debug('copying {0} to {1}'.format(src, dst))
        return do('sudo cp -R {0} {1}'.format(src, dst)) if recurse \
            else do('sudo cp {0} {1}'.format(src, dst))

    # TODO: depracate this useless thing...
    def make_package_paths(self, pkg_dir, tmp_dir):
        """
        DEPRACATED!
        creates directories for managing packages
        """
        # this is stupid... remove it soon...
        lgr.debug('creating package directories')
        self.mkdir('%s/archives' % tmp_dir)
        self.mkdir(pkg_dir)

    def tar(self, chdir, output_file, input_path):
        """
        tars an input file or directory

        :param string chdir: change to this dir before archiving
        :param string output_file: tar output file path
        :param string input: input path to create tar from
        """
        lgr.debug('tar-ing {0}'.format(output_file))
        do('sudo tar -C {0} -czvf {1} {2}'.format(chdir, output_file,
                                                  input_path))

    def untar(self, chdir, input_file):
        """
        untars a dir

        :param string chdir: change to this dir before extracting
        :param string input_file: file to untar
        """
        lgr.debug('tar-ing {0}'.format(input_file))
        do('sudo tar -C {0} -xzvf {1}'.format(chdir, input_file))


class PythonHandler(CommonHandler):
    """
    python operations handler
    """
    def pip(self, module, dir=False):
        """
        pip installs a module

        :param string module: python module to ``pip install``
        :param string dir: (optional) if ommited, will use system python
         else, will use `dir` (for virtualenvs and such)
        """
        lgr.debug('installing module {0}'.format(module))
        return do('sudo {0}/pip --default-timeout=45 install {1}'
                  ' --process-dependency-links'.format(dir, module)) \
            if dir else do('sudo pip --default-timeout=45 install {1}'
                           ' --process-dependency-links'.format(dir, module))

    def get_python_module(self, module, dir=False, venv=False):
        """
        downloads a python module

        :param string module: python module to download
        :param string dir: (optional) if ommited, will use system python
         else, will use `dir` (for virtualenvs and such)
        """
        lgr.debug('downloading module {0}'.format(module))
        return do('sudo {0}/pip install --no-use-wheel'
                  ' --process-dependency-links --download "{1}/" {2}'
                  .format(venv, dir, module)) \
            if venv else do('sudo /usr/local/bin/pip install --no-use-wheel'
                            ' --process-dependency-links --download "{0}/" {1}'
                            .format(dir, module))

    def check_module_installed(self, name, dir=False):
        """
        checks to see that a module is installed

        :param string name: module to check for
        :param string dir: (optional) if ommited, will use system python
         else, will use `dir` (for virtualenvs and such)
        """
        lgr.debug('checking whether {0} is installed'.format(name))
        x = do('pip freeze', capture=True) if not dir else \
            do('{0}/pip freeze'.format(dir), capture=True)
        if re.search(r'{0}'.format(name), x.stdout):
            lgr.debug('module {0} is installed'.format(name))
            return True
        else:
            lgr.debug('module {0} is not installed'.format(name))
            return False

    # TODO: support virtualenv --relocate
    # TODO: support whack http://mike.zwobble.org/2013/09/relocatable-python-virtualenvs-using-whack/ # NOQA
    def venv(self, venv_dir):
        """
        creates a virtualenv

        :param string venv_dir: venv path to create
        """
        lgr.debug('creating virtualenv in {0}'.format(venv_dir))
        if self.check_module_installed('virtualenv'):
            do('virtualenv {0}'.format(venv_dir))
        else:
            lgr.error('virtualenv is not installed. terminating')
            sys.exit()


class RubyHandler(CommonHandler):
    # TODO: remove static paths for ruby installations..
    def get_ruby_gem(self, gem, dir=False):
        """
        downloads a ruby gem

        :param string gem: gem to download
        :param string dir: directory to download gem to
        """
        lgr.debug('downloading gem {0}'.format(gem))
        return do('sudo gem install --no-ri --no-rdoc'
                  ' --install-dir {0} {1}'.format(dir, gem))


class AptHandler(CommonHandler):
    def dpkg_name(self, dir):
        """
        renames deb files to conventional names

        :param string dir: dir to review
        """

        lgr.debug('renaming deb files...')
        do('dpkg-name {0}/*.deb'.format(dir))

    # TODO: fix this... (it should dig a bit deeper)
    def check_if_package_is_installed(self, package):
        """
        checks if a package is installed

        :param string package: package name to check
        :rtype: `bool` representing whether package is installed or not
        """

        lgr.debug('checking if {0} is installed'.format(package))
        try:
            do('sudo dpkg -s {0}'.format(package))
            lgr.debug('{0} is installed'.format(package))
            return True
        except:
            lgr.error('{0} is not installed'.format(package))
            return False

    def apt_download_reqs(self, reqs, sources_path):
        """
        downloads component requirements

        :param list reqs: list of requirements to download
        :param sources_path: path to download requirements to
        """
        for req in reqs:
            self.apt_download(req, sources_path)

    def apt_autoremove(self, pkg):
        """
        autoremoves package dependencies

        :param string pkg: package to remove
        """
        lgr.debug('removing unnecessary dependencies...')
        do('sudo apt-get -y autoremove {0}'.formaT(pkg))

    def apt_download(self, pkg, dir):
        """
        uses apt to download package debs from ubuntu's repo

        :param string pkg: package to download
        :param string dir: dir to download to
        """
        lgr.debug('downloading {0} to {1}'.format(pkg, dir))
        do('sudo apt-get -y install {0} -d -o=dir::cache={1}'.format(pkg, dir))

    def add_src_repo(self, url, mark):
        """
        adds a source repo to the apt repo

        :param string url: url to add to sources list
        :param string mark: package mark (stable, etc...)
        """
        lgr.debug('adding source repository {0} mark {1}'.format(url, mark))
        do('sudo sed -i "2i {0} {1}" /etc/apt/sources.list'.format(mark, url))

    def add_ppa_repo(self, url):
        """
        adds a ppa repo to the apt repo

        :param string url: ppa url to add
        """
        lgr.debug('adding ppa repository {0}'.format(url))
        do('add-apt-repository -y {0}'.format(url))

    def add_key(self, key_file):
        """
        adds a key to the local repo

        :param string key_file: key file path
        """
        lgr.debug('adding key {0}'.format(key_file))
        do('sudo apt-key add {0}'.format(key_file))

    @staticmethod
    def apt_update():
        """
        runs apt-get update
        """
        lgr.debug('updating local apt repo')
        do('sudo apt-get update')

    def apt_get(self, packages):
        """
        apt-get installs a package

        :param list packages: packages to install
        """
        for package in packages:
            lgr.debug('installing {0}'.format(package))
            do('sudo apt-get -y install {0}'.format(package))

    def apt_purge(self, package):
        """
        completely purges a package from the local repo

        :param string package: package name to purge
        """
        lgr.debug('attemping to purge {0}'.format(package))
        do('sudo apt-get -y purge {0}'.format(package))


class DownloadsHandler(CommonHandler):
    def wget(self, url, dir=False, file=False):
        """
        wgets a url to a destination directory or file

        :param string url: url to wget?
        :param string dir: download to dir....
        :param string file: download to file...
        """
        
        options = '--timeout=30'
        lgr.debug('downloading {0} to {1}'.format(url, dir))
        try:
            if (file and dir) or (not file and not dir):
                lgr.warning('please specify either a directory'
                            ' or file to download to.')
                sys.exit(1)
            do('sudo wget {0} {1} -O {2}'.format(url, options, file)) if file \
                else do('sudo wget {0} {1} -P {2}'.format(url, options, dir))
        except:
            lgr.error('failed downloading {0}'.format(url))


class TemplateHandler(CommonHandler):
    # TODO: replace this with method generate_from_template()..
    def create_bootstrap_script(self, component, template_file, script_file):
        """
        creates a script file from a template file

        ..note: DEPRACTE - this should be merged with `generate_from_template`

        :param dict component: contains the params to use in the template
        :param string template_file: template file path
        :param string script_file: output path for generated script
        """
        lgr.debug('creating bootstrap script...')
        formatted_text = self._template_formatter(
            defs.PACKAGER_TEMPLATE_PATH, template_file, component)
        self._make_file(script_file, formatted_text)

    def generate_configs(self, component):
        """
        generates configuration files from templates

        # TODO: document configuration file creation method
        :param dict component: contains the params to use in the template
        """
        # iterate over the config_templates dict in the package's config
        for key, value in component['config_templates'].iteritems():
            # we'll make some assumptions regarding the structure of the config
            # placement. spliting and joining to make up the positions.

            # and find something to mark that you should generate a template
            # from a file
            if key.startswith('__template_file'):
                # where should config reside within the package?
                config_dir = value['config_dir']  # .split('_')[0]
                # where is the template dir?
                template_dir = '/'.join(value['template']
                                        .split('/')[:-1])
                # where is the template file?
                template_file = value['template'].split('/')[-1]
                # the output file's name is...
                output_file = value['output_file'] \
                    if 'output_file' in value \
                    else '.'.join(template_file.split('.')[:-1])
                # and its path is...
                output_path = '{0}/{1}/{2}'.format(
                    component['sources_path'], config_dir, output_file)
                # create the directory to put the config in after it's
                # genserated
                self.mkdir('{0}/{1}'.format(
                    component['sources_path'], config_dir))
                # and then generate the config file. WOOHOO!
                self.generate_from_template(component,
                                            output_path,
                                            template_file,
                                            template_dir)
            # or generate templates from a dir, where the difference
            # would be that the name of the output files will correspond
            # to the names of the template files (removing .template)
            elif key.startswith('__template_dir'):
                config_dir = value['config_dir']  # .split('_')[0]
                template_dir = value['templates']
                # iterate over the files in the dir...
                # and just perform the same steps as above..
                for subdir, dirs, files in os.walk(template_dir):
                    for file in files:
                        template_file = file
                        output_file = '.'.join(template_file.split('.')[:-1])
                        output_path = '{0}/{1}/{2}'.format(
                            component['sources_path'], config_dir, output_file)

                        self.mkdir('{0}/{1}'.format(
                            component['sources_path'], config_dir))
                        self.generate_from_template(component,
                                                    output_path,
                                                    template_file,
                                                    template_dir)
            elif key.startswith('__config_dir'):
                config_dir = value['config_dir']
                files_dir = value['files']
                self.mkdir('{0}/{1}'.format(
                    component['sources_path'], config_dir))
                self.cp(files_dir + '/*', component['sources_path'] + '/'
                        + config_dir)

    def generate_from_template(self, component, output_file, template_file,
                               templates=defs.PACKAGER_TEMPLATE_PATH):
        """
        generates configuration files from templates using jinja2
        http://jinja.pocoo.org/docs/

        :param dict component: contains the params to use in the template
        :param string output_file: output file path
        :param string template_file: template file name
        :param string templates: template files directory
        """
        lgr.debug('generating config file...')
        formatted_text = self._template_formatter(
            templates, template_file, component)
        self._make_file(output_file, formatted_text)

    def _template_formatter(self, template_dir, template_file, var_dict):
        """
        receives a template and returns a formatted version of it
        according to a provided variable dictionary
        """
        env, template = None, None
        env = Environment(loader=FileSystemLoader(template_dir)) \
            if self.is_dir(template_dir) else lgr.error('template dir missing')
        template = env.get_template(template_file) \
            if self.is_file(template_dir + '/' + template_file) \
            else lgr.error('template file missing')

        if env is not None and template is not None:
            lgr.debug('generating template from {0}/{1}'.format(
                      template_dir, template_file))
            return(template.render(var_dict))
        else:
            lgr.error('could not generate template')
            sys.exit(1)

    def _make_file(self, output_path, content):
        """
        creates a file from content
        """
        if config.PRINT_TEMPLATES:
            lgr.debug('creating file: {0} with content: \n{1}'.format(
                      output_path, content))
        with open('{0}'.format(output_path), 'w+') as f:
            f.write(content)


class PackagerError(Exception):
    pass


def main():

    lgr.debug('running in main...')

if __name__ == '__main__':
    main()