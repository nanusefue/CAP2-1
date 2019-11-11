import luigi
import os
import sys
import subprocess
import logging
import yaml

logger = logging.getLogger('luigi-interface')


class SpecificationError(Exception):
    pass


class CondaEnv(luigi.Task):
    base_path = luigi.Parameter(default="vendor/conda")
    name = luigi.Parameter()
    python = luigi.IntParameter(default=3)

    spec_dir = luigi.Parameter(default="config/envs")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = os.path.join(self.base_path, self.name)
        self.spec_file = os.path.abspath(os.path.join(
            self.spec_dir, '{}.yml'.format(self.name)
        ))
        print(os.getcwd())
        assert self.has_spec()
        if not os.path.isdir(self.spec_dir):
            os.makedirs(self.spec_dir)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)

    @property
    def bin(self):
        return os.path.join(self.path, "bin")

    def get_path(self, tool):
        return os.path.join(self.bin, tool)

    def has_spec(self):
        return os.path.isfile(
            self.spec_file
        )

    def save_spec(self):
        proc = subprocess.Popen(
            ' '.join(['conda', 'env', 'export', '--name', self.name]),
            stdout=subprocess.PIPE,
            shell=True
        )
        stdout = proc.communicate()[0]

        # the output of conda env export itself is only a valid
        # env description if, the line starting with "prefix: " is removed
        with open(self.spec_file, 'w') as f:
            for line in stdout.decode('utf-8').splitlines():
                if "prefix: " in line:
                    continue

                f.write(line)
                f.write('\n')

    def contains(self, package):
        try:
            with open(self.spec_file, 'r') as f:
                deps = yaml.load(f)
                deps = deps.get('dependencies', [])

            while True:
                try:
                    dep = deps.pop()
                except IndexError:
                    break

                try:
                    if dep.startswith(package):
                        return True
                except AttributeError:
                    deps += [x for x in dep.values()][0]

            return False

        except FileNotFoundError:
            return False

    def install(self, package, channel="anaconda"):
        cmd = [
            'conda', 'install',
            '-p', self.path,
            '-c', channel,
            package, '-y'
        ]
        logger.info('installing: {} with {}'.format(package, ' '.join(cmd)))
        try:
            subprocess.check_call(' '.join(cmd), shell=True)
        except:
            print(f'Subprocess failed from {os.getcwd()}: {cmd}', file=sys.stderr)
            raise
        self.save_spec()

    def run(self):
        """
        init conda env
        """
        if self.has_spec():
            cmd = [
                'conda', 'env', 'create', '-f',
                self.spec_file, '-p', self.path, "python={}".format(self.python),
            ]
            logger.info('init conda env: {}'.format(' '.join(cmd)))
            subprocess.check_call(cmd)
        else:
            cmd = [
                'conda', 'create', '-p', self.path, "python={}".format(self.python), '-y'
            ]
            logger.info('init conda env: {}'.format(' '.join(cmd)))
            try:
                subprocess.check_call(' '.join(cmd), shell=True)
            except:
                print(f'Subprocess failed from {os.getcwd()}: {cmd}', file=sys.stderr)
                raise
            self.save_spec()

    def complete(self):
        logger.debug("{}: self.complete() => ispath({}) = {} ".format(str(self), self.path, os.path.isdir(self.path)))
        return os.path.isdir(self.path)


class CondaPackage(luigi.Task):
    package = luigi.Parameter()

    executable = luigi.Parameter()

    channel = luigi.Parameter(default="anaconda")
    env = luigi.Parameter(default="CAP_v2")
    version = luigi.Parameter(default="None")
    python = luigi.IntParameter(default=3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._env = CondaEnv(name=self.env, python=self.python)
        self.bin = os.path.join(
            self._env.bin, self.executable
        )

    def requires(self):
        return self._env

    def output(self):
        return luigi.LocalTarget(
            self.bin
        )

    def complete(self):
        return self.output().exists()

    def related_tool(self, name):
        return self._env.get_path(name)

    def run(self):
        if not self._env.contains(self.package):
            self._env.install(self.package, self.channel)

        if not self.output().exists():
            raise SpecificationError(
                f'Tool {self.package} was not correctly installed'
            )
