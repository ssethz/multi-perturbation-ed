# "Near-Optimal Multi-Perturbation ExperimentalDesign for Causal Structure Learning"
Efficient algorithms for selecting multiple perturbation experiments for the task of causal structure discovery.

To run on our cluster:
"bsub -W 2:00 -n 4 -R "rusage[mem=250]" "python3 main.py""

For repeats:
"for i in {1..50}; do bsub -W 6:00 -n 1 -R "rusage[mem=250]" "python3 main.py $i"; done"

Files to be run for experiments take in the random seed as the first input argument so multiple repeats can be done in parallel. 

Description of files:

main.py: contains all necessary functions for infinite sample experiments (including DREAM) and the 
    core algorithms of the project. Run to carry-out infinite sample experiments. 
finite_cd.py: contains machinary specific to finite sample experiments. Run to carry-out finite sample experiments.
finite.py: contains some helper functions for fiite experiments, such as generating DAGs with linear SEMs and computing the BIC of a model.
mec_size.py: contains functions for sampling from an MEC or enumerating an MEC
represent.py: a script with some functions for plotting the results of experiments

Notation:
For the paper, number of variables per intervention was denoted q and batch size denoted m. In the code, we denote number of variables per intervention as k and the batch size as b or n_b. 