#!/usr/bin/python
import sys
import os
from os.path import join
import argparse
from subprocess import Popen, PIPE, STDOUT
import requests
import tarfile

import toml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='Parse arguments from config file')
    parser.add_argument('--bed', type=str, help='path to microarray bed file (multiple files e.g. via `foo_{1:22}.bed`)')
    parser.add_argument('--bim', type=str, help='path to microarray bim file (multiple files e.g. via `foo_{1:22}.bim`)')
    parser.add_argument('--fam', type=str, help='path to microarray fam file')
    parser.add_argument('--cov', type=str, help='path to space-separated covariate file; first two columns should be FID and IID')
    parser.add_argument(
            '--model',
            type=str,
            default='lmmInfOnly',
            choices=['lmm', 'lmmInfOnly', 'lmmForceNonInf'],
            help="what lmm model to use in BOLT-LMM. "
            "`lmm` will run non-inf model only if increase in power expected; "
            "`lmmInfOnly` will run only inf-model (fast); "
            " and `lmmForceNonInf` will always run both models",
            )
    parser.add_argument(
            '--cov_cols',
            type=str,
            default=['sex', 'assessment_center', 'geno_batch'],
            nargs='+',
            help='categorical covariate columns in covariate file. Defaults to sex, assessment_center and geno_batch',
            )
    parser.add_argument(
            '--qcov_cols',
            type=str,
            default=['age', 'genet_PC_{1:10}'],
            nargs='+',
            help='categorical covariate columns in covariate file',
            )
    parser.add_argument(
            '--emb',
            type=str,
            help='path to space-separated image embedding file; first two columns should be FID and IID, afterwards columns should be named `PC_0`, `PC_1`, ...',
            )
    parser.add_argument(
            '--first_pc',
            type=int,
            default=0,
            help='will run BOLT-LMM on `first_pc` to `last_pc`. Default: 0',
            )
    parser.add_argument(
            '--last_pc',
            type=int,
            default=9,
            help='will run BOLT-LMM on `first_pc` to `last_pc`. Default: 9',
            )
    parser.add_argument('--out_dir', type=str, help='path to output directory')
    parser.add_argument('--out_fn', type=str, default='PC_%d.txt', help='output filename; should include a `%d` for the PC')
    parser.add_argument('--bolt', type=str, help='path to BOLT-LMM directory. If none specified, will try to download bolt-lmm to `bolt/`')
    parser.add_argument('--threads', default=130, type=int, help='how many threads to use for BOLT-LMM')
    # parser.add_argument('--maf', default=0.001, type=float, help='Minor allele frequency in microarray data.')
    # parser.add_argument('--ldr2', default=0.8, type=float, help='R^2 for LD-pruning of microarray SNPs.')
    # parser.add_argument('--hwe', default=0.00001, type=float, help='Hardy-Weinberg p-value for microarray data')
    parser.add_argument('--max_missing_snp', default=0.1, type=float, help='maximum missingness per SNP')
    parser.add_argument('--max_missing_indiv', default=0.1, type=float, help='maximum missingness per individual')
    parser.add_argument('--ref_map', type=str, help='Alternative genome reference map. If none specified, will use GRCh37/hg19 map from BOLT-LMM')
    parser.add_argument('--ldscores', type=str, help='LDScores for test calibration. If none specified, will use European ancestry scores from BOLT-LMM')


    parser.add_argument('--run_imputed', action='store_true', help='Set flag if you want to run analysis on imputed data')
    parser.add_argument('--out_fn_imp', default='PC_%d.imp.txt', type=str, help='output filename for imputed; should include a `%d` for the PC')
    parser.add_argument('--bgen', type=str, help='path to imputed .bgen files. Multiple files via `foo_{1:22}.bgen`')
    parser.add_argument('--sample', type=str, help='path to imputed .sample files. Multiple files via `foo_{1:22}.sample`')
    parser.add_argument('--imp_maf', default=0.001, type=float, help='Minor allele frequency in imputed data.')
    parser.add_argument('--imp_info', default=0.001, type=float, help='Imputation information quality score in imputed data.')
    parser.add_argument(
            '--remove',
            type=str,
            default=[],
            nargs='+',
            help='IID to remove. Space-separated file with `FID` and `IID`, one FID/IID-pair per line',
            )



    args = parser.parse_args()


    if args.config is not None:
        configs = toml.load(args.config)
        covars = configs.pop('covColumns')
        qcovars = configs.pop('qCovColumns')
        bolt = check_bolt(configs.pop('boltDirectory'))
        out_dir = configs.pop('outputDirectory')
        out_fn = configs.pop('outputFn')
        out_imp = configs.pop('outputFnImp')
        run_imputed = configs.pop('runImputed')
        if not run_imputed:
            configs.pop('bgenFile')
            configs.pop('sampleFile')
            configs.pop('bgenMinMAF')
            configs.pop('bgenMinINFO')
        flags = [f"--{configs.pop('model')}"]
        first, last = configs.pop('firstPC'), configs.pop('lastPC')
        remove = configs.pop('remove')


    else:
        covars = args.cov_cols
        qcovars = args.qcov_cols
        bolt = check_bolt(args.bolt)
        out_dir = args.out_dir
        out_fn = args.out_fn if args.out_fn else 'PC_%d.txt'
        out_imp = args.out_fn_imp if args.out_fn_imp else 'PC_%d.imp.txt'
        run_imputed = args.run_imputed
        first, last = args.first_pc, args.last_pc
        remove = args.remove
        configs = {
                'bed': args.bed,
                'bim': args.bim,
                'fam': args.fam,
                'phenoFile': args.emb,
                'covarFile': args.cov,
                'maxMissingPerSnp': args.max_missing_snp,
                'maxMissingPerIndiv': args.max_missing_indiv,
                'geneticMapFile': args.ref_map,
                'LDscoresFile': args.ldscores,
                'numThreads': args.threads,
                }
        flags = [f'--{args.model}']

        if run_imputed:
            configs['bgenFile'] = args.bgen
            configs['sampleFile'] = args.sample
            configs['bgenMinMAF'] = args.imp_maf
            configs['bgenMinINFO'] = args.imp_info

        if not args.ref_map:
            configs['geneticMapFile'] = join(bolt, 'tables', 'genetic_map_hg19_withX.txt.gz')
        if not args.ldscores:
            configs['LDscoresFile'] = join(bolt, 'tables', 'LDSCORE.1000G_EUR.tab.gz')


    pcs = range(first, last+1)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(join(out_dir, 'log'), exist_ok=True)
    for pc in pcs:
        configs['phenoCol'] = f'PC_{pc}'
        configs['statsFile'] = join(out_dir, out_fn % pc)
        log_file = join(out_dir, 'log', f'PC_{pc}.log')
        if run_imputed:
            configs['statsFileBgenSnps'] = join(out_dir, out_imp % pc)

        run_single_bolt(bolt, flags, covars, qcovars, remove, log_file, **configs)

def check_bolt(pth):
    if not pth:
        pth = 'BOLT-LMM_v2.3.4'
    if not os.path.isdir(pth):
        b_tgz = 'bolt.tar.gz'
        print('downloading BOLT-LMM ...')
        request = requests.get('https://storage.googleapis.com/broad-alkesgroup-public/BOLT-LMM/downloads/BOLT-LMM_v2.3.4.tar.gz')
        open(b_tgz, 'wb').write(request.content)
        print('finished download')
        tar = tarfile.open(b_tgz, 'r:gz')
        tar.extractall('/'.join(pth.strip('/').split('/')[:-1]))
        tar.close()
        os.remove(b_tgz)
    return pth


def run_single_bolt(bolt, flags, covars, qcovars, remove, log_file, **kwargs):

    config = sum([[f'--{key}', f'{value}'] for key, value in kwargs.items()], [])
    for c in covars: config += ['--covarCol', c]
    for q in qcovars: config += ['--qCovarCol', q]
    if isinstance(remove, str) and remove:
        remove = [remove]
    for r in remove: config += ['--remove', r]
    config += '--covarMaxLevels 50'.split()
    config += ['--verboseStats']

    cmd = [join(bolt, 'bolt')] + flags + config
    print(cmd)
    with Popen(cmd, stdout=PIPE, stderr=STDOUT) as p, open(log_file, 'wb') as f:
        for line in p.stdout:
            sys.stdout.buffer.write(line)
            f.write(line)
    # process = Popen(cmd, stdout=PIPE)
    # stdout, stderr = process.communicate()
    # print('stdout:')
    # print(stdout)

    # print('stderr:')
    # print(stderr)


if __name__ == '__main__':
    # pass
    main()