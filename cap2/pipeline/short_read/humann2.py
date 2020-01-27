
import luigi
import subprocess
from os.path import join, dirname, basename

from ..utils.cap_task import CapTask
from ..config import PipelineConfig
from ..utils.conda import CondaPackage
from ..databases.uniref import Uniref90
from ..preprocessing.clean_reads import CleanReads


class MicaUniref90(CapTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pkg = CondaPackage(
            package="diamond",
            executable="diamond",
            channel="bioconda"
        )
        self.config = PipelineConfig(self.config_filename)
        self.out_dir = self.config.out_dir
        self.db = Uniref90(config_filename=self.config_filename)
        self.reads = CleanReads(
            sample_name=self.sample_name,
            pe1=self.pe1,
            pe2=self.pe2,
            config_filename=self.config_filename
        )

    def requires(self):
        return self.pkg, self.db, self.reads

    def output(self):
        m8 = luigi.LocalTarget(
            join(self.out_dir, f'{self.sample_name}.uniref90.m8.gz')
        )
        m8.makedirs()
        return {
            'm8': m8,
        }

    def run(self):
        cmd = (
            f'{self.pkg.bin} blastx '
            f'--threads {self.cores} '
            f'-d {self.db.diamond_index} '
            f'-q {self.reads.output()["clean_reads"][0]} '
            '--block-size 6 '
            f'| gzip > {self.output()["m8"].path} '
        )
        subprocess.check_call(cmd, shell=True)


class Humann2(CapTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pkg = CondaPackage(
            package="humann2",
            executable="humann2",
            channel="bioconda"
        )
        self.config = PipelineConfig(self.config_filename)
        self.out_dir = self.config.out_dir
        self.alignment = MicaUniref90(
            sample_name=self.sample_name,
            pe1=self.pe1,
            pe2=self.pe2,
            config_filename=self.config_filename
        )

    def requires(self):
        return self.pkg, self.alignment

    def output(self):
        genes = luigi.LocalTarget(
            join(self.out_dir, f'{self.sample_name}.humann2.genes.tsv')
        )
        path_abunds = luigi.LocalTarget(
            join(self.out_dir, f'{self.sample_name}.humann2.path_abunds.tsv')
        )
        path_covs = luigi.LocalTarget(
            join(self.out_dir, f'{self.sample_name}.humann2.path_covs.tsv')
        )
        genes.makedirs()
        return {
            'genes': genes,
            'path_abunds': path_abunds,
            'path_covs': path_covs,
        }

    def run(self):
        odir = params.sample_name + '_humann2'
        genes = odir + '/*genefamilies.tsv'
        abunds = odir + '/*pathabundance.tsv'
        covs = odir + '/*pathcoverage.tsv'
        cmd = (
            f'{self.pkg.bin} '
            f'--input {self.alignment.output()["m8"].path} '
            f'--output {self.sample_name}_humann2 ; '
            'mv ' + genes + ' ' + self.output()['genes'].path + '; '
            'mv ' + abunds + ' ' + self.output()['path_abunds'].path + '; '
            'mv ' + covs + ' ' + self.output()['path_covs'].path + '; '
            f'rm -r {self.sample_name}_humann2;'
        )
        subprocess.check_call(cmd, shell=True)
