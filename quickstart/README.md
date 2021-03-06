# Quickstart guide


This directory will help you test transferGWAS if you don't have any data (however, you need access to a GPU for the deep learning parts). The script `prep_geno.py` creates genetic dummy data and config files which you can use to run a transferGWAS on synthetic images. Note that this is **not** the simulation study that we used in the paper, but only a way for you to get started if you don't have fast access to real genetic data.

The script `prep_geno.py` lets you create (very unrealistic) dummy individuals with synthetic genetic data, covariates, and a config file to run a simulation study.
First, you will have to have downloaded the models and BOLT-LMM via

```bash
../download_models.sh
```
 
Next, you create the dummy genetic data via (make sure to have the included conda environment activated):
```bash
python prep_geno.py \
    --sample_size 5000 \
    --n_geno 100000 \
    --n_causal 100 \
    --exp_var 0.5 \
    --seed 123 \
    --threads 8
```
This command will create a directory `runs/run_{RUN_ID}/` (with some random `RUN_ID`) which contains the dummy data as well as a `config.toml` configuration file.

Now you can run a simulation experiment on this dummy data (with synthetically generated retina scans using a StyleGAN2) using:
```bash
python ../simulation/run_simulation.py runs/run_{RUN_ID}/config.toml --stages 1 2 3 4 5 --verbose
```
where you have to insert your `RUN_ID` from the previous step.
Final results and intermediate steps are all saved in `runs/run_{RUN_ID}/`.
This command will run all steps of the simulation study as detailed in `../simulation_study/README.md`. Note that you will need access to a CUDA-enabled GPU for this to work!

The final association results will be saved in `runs/run_{RUN_ID}/results/aggregate_exp[...].txt` (with parameters instead of `[...]`) and the true causal SNPs are in `runs/run_{RUN_ID}/causal_variants.csv`. You can get a more complete picture in python:
```python
import pickle
RUN_ID = TODO
seed = 123
n_causal = 100
exp_var = 0.5
latent_code, _, _, _, W, _ = pickle.load(open('runs/run_{RUN_ID}/latent/exp_var{exp_var}_nc{n_causal}_seed{seed}.pkl', 'rb'))
```
Here, `W` will hold the effet sizes per dimension for the causal SNPs (ordered as in the `causal_variants.csv` file), and latent code will be the true latent code fed into the GAN.

With the default setting, an exemplar run recovered 29 of the 100 causal SNPs at `alpha = 5e-8`, and 37 are significant at `alpha = 5e-7` (Bonferroni threshold for 100,000 SNPs and uncorrected significance threshold 0.05).


Note that this is very far from a realistic simulation study; genetic data is modeled completely without LD and any other kinds of structure.
For a more realistic simulation, you can provide real genetic data as explained in `../simulation/README.md` in more detail.


### Runtime

Generation of the synthetic genetic data grows linearly in sample size and number of genotypes; for the suggested setting (`sample_size = 5000`, `n_geno = 100000`), this should take <5 minutes on most reasonable systems.

The simulation consists of several steps.
1. Creation of latent representations from genetic data: <30 seconds
2. Synthetic images from latent representation via StyleGAN2: <5 minutes (depends on GPU)
3. Feature condensation using ResNet50: <15 minutes (depends on GPU)
4. BOLT-LMM GWAS: 10 times ~1 minute (depends on the number of threads chosen)
5. Aggregation: <30 seconds


