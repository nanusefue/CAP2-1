
import luigi
import subprocess
from os.path import join, dirname, basename
from yaml import load

from ..config import PipelineConfig
from ..utils.conda import CondaPackage
from ..utils.cap_task import CapTask
from .map_to_human import RemoveHumanReads


class ErrorCorrectReads(CapTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pkg = CondaPackage(
            package="spades",
            executable="spades.py",
            channel="bioconda"
        )
        self.config = PipelineConfig(self.config_filename)
        self.out_dir = self.config.out_dir
        self.nonhuman_reads = RemoveHumanReads(
            pe1=self.pe1,
            pe2=self.pe2,
            sample_name=self.sample_name,
            config_filename=self.config_filename,
        )

    def requires(self):
        return self.pkg, self.nonhuman_reads

    def output(self):
        return {
            'error_corrected_reads': [
                self.get_target(self.sample_name, 'error_corrected_reads', 'R1', 'fastq.gz'),
                self.get_target(self.sample_name, 'error_corrected_reads', 'R2', 'fastq.gz'),
            ],
        }

    def run(self):
        r1, r2 = self.nonhuman_reads.output()['nonhuman_reads']
        cmd = self.pkg.bin
        cmd += f' --only-error-correction --meta -1 {r1.path} -2 {r2.path}'
        cmd += f' -t {self.cores} -o {self.sample_name}.error_correction_out'
        subprocess.check_call(cmd, shell=True)  # runs error correction but leaves output in a dir
        config_path = f'{self.sample_name}.error_correction_out/corrected/corrected.yaml'
        spades_out = load(open(config_path).read())
        ec_r1 = spades_out[0]['left reads']
        assert len(ec_r1) == 1
        ec_r2 = spades_out[0]['right reads']
        assert len(ec_r2) == 1
        paths = self.output()['error_corrected_reads']
        cmd = f'mv {ec_r1[0]} {paths[0].path} && mv {ec_r2[0]} {paths[1].path}'
        subprocess.check_call(cmd, shell=True)
