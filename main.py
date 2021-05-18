import numpy as np 
import itertools
import scipy.optimize
import networkx as nx
import matplotlib.pyplot as plt
import math
from matplotlib.lines import Line2D
import time
import params
import json
import sys
import mec_size
import networkx.algorithms.approximation.vertex_cover as vertex_cover
import dream

"""
Represented by a binary matrix where m[i, j]= 1 iff i->j, else 0

PCDAG objects: 
Represented by an integer matrix where m[i, j]= 1 iff i->j, -1 iff i-j (and edge no known), else 0

Weight matrices:
For linear models we store the weights as a matrix of floats. For infinite samples we don't need a weight matrix. 

Noise:
Noise scales in gaussian linear models are stored as a vectors of floats
"""

def generate_chain_dag_no_colliders(n):
    """
    generates a DAG that is just a chain with no colliders. 
    input:
    int n: number of nodes
    output:
    matrix: chain dag with no unshielded colliders
    """
    return np.eye(n, k=1, dtype=np.int32) #k=1 since we just fill in the upper diagonal

def generate_chain_dag_fixed_root(n, v):
    """
    generates a DAG that is just a chain with no colliders, but may not just be directions
    left to right (the root vertex is random). 
    input:
    int n: number of nodes
    output:
    matrix: chain dag with no unshielded colliders
    """
    dag_temp = np.zeros((n,n))

    for i in range(0, v):
        dag_temp[i+1, i] = 1

    for i in range(v, n-1):
        dag_temp[i, i+1] = 1

    return dag_temp

def generate_scale_free(n, alpha=0.41, beta=0.54):
    """
    generates a general directed scale-free graph
    int n: size of network
    float alpha: prob adding new node to existing node

    float beta:Probability for adding an edge between two existing nodes. 
    One existing node is chosen randomly according the in-degree distribution 
    and the other chosen randomly according to the out-degree distribution.
    
    """

    #gamma is alpha-beta and doesn't need be specified in function call
    #gamma:Probability for adding a new node connected to an existing node chosen randomly 
    #according to the out-degree distribution
    g = nx.scale_free_graph(n, alpha, beta, 1-alpha-beta)

    #turn to undirected, generate a random ordering, remove self cycles, orient
    ordering = np.arange(n)
    np.random.shuffle(ordering) 
    
    dag = np.zeros((n, n))
    G = nx.to_numpy_matrix(g)

    for i in range(n):
        for j in range(i, n):
            if i == j:
                dag[i][j] = 0
            elif G[i,j] >= 1 or G[j,i] >= 1:
                if ordering[i] > ordering[j]:
                    dag[j][i] = 1
                    dag[i][j] = 0
                else:
                    dag[i][j] = 1
                    dag[j][i] = 0

    return dag

def generate_barabasi_albert(n, m1, m2=1, p=1):
    #Generates a scale-free dag using the Barabasi-Albert Model
    #each node is attached to m1 times with prob p, else p2 times
    #0 will always be the root
    g = nx.dual_barabasi_albert_graph(n, m1, m2, p)
    dag = np.triu(nx.to_numpy_matrix(g), k=1)
    np.random.shuffle(dag)
    return dag


def uniform_random_tree(n):
    """
    generates tree MEC uniformly, then picks a node to be the root
    https://nokyotsu.com/qscripts/2008/05/generating-random-trees-and-connected.html
    input:
    int n: tree size
    output:
    matrix: dag with tree mec
    """
    cpdag = np.zeros((n, n))

    src = []
    dst = np.random.permutation(np.arange(n)).tolist()
    src.append(dst.pop()) # picks the root

    while(len(dst)>0):
        a = np.random.choice(src) #random element in src
        b = dst.pop()
        # add edge a,b
        cpdag[a][b] = -1
        cpdag[b][a] = -1
        src.append(b)

    #now randomly pick root and orient
    dag_temp = orient_tree_root_v(cpdag, np.random.choice(n))

    return dag_temp


def generate_k_star_system(n, k):
    """
    generates a forest of k stars
    """
    dag = np.zeros((n,n))
    r = int(math.ceil(n/k))
    host = 0 
    nodes = np.arange(n)
    np.random.shuffle(nodes)

    for i in range(n):
        if i%r == 0:
            host = i
        else:
            #start undirected
            dag[nodes[host], nodes[i]] = 1

    return dag

def generate_fully_connected(n):
    """
    generate a fully connected dag with a fully connected mec (no colliders)
    input:
    int n, number of nodes
    output:
    matrix dag
    """
    #take matrix of all ones, removes the diagonal and below
    #only generates DAGs where the ordering is the ordering of the nodes
    #but this is fine since all methods are agnostic to this symmetry
    dag = np.triu(np.ones(n),k=1)
    return dag

def ER_bipartite(n, m, p):
    """
    constructs a bipartite graph under an ER-like model
    input:
    int n: the number of nodes in set one
    int m: the number of nodes in set 2
    float p: the edge probability param
    """
    #strategy: generate undirected graph and remove all below diagonal
    nx_dag = nx.bipartite.random_graph(n, m, p, directed=False)

    return np.triu(nx.to_numpy_array(nx_dag), 1)

def generate_ER(n, p):
    """
    generates a dag using an Erdos renyi model
    first generates a random ordering, then
    input:
    int n, number of nodes
    float p, probability of each edge appearing
    output:
    matrix dag
    """
    ordering = np.arange(n)
    np.random.shuffle(ordering) 
    #each element ordering[i] is node indexd by i's place in the ordering

    dag = np.zeros((n,n))

    for i in range(n):
        for j in range(i, n):
            if i == j:
                continue
            if np.random.binomial(1, p) == 1:
                if ordering[i] > ordering[j]:
                    dag[j,i] = 1
                else:
                    dag[i,j] = 1

    return dag

def generate_chain_dag(n):
    """
    generates a chain DAG that may have colliders. generated by permuting variables 
    input:
    int n: number of nodes
    output:
    matrix: chain dag potentially with shielded colliders
    """
    #the nodes go in order but we just sample randomly whether the arrow goes forwards or backwards
    forward_backwards = np.random.binomial(1, 0.5, n)
    dag = np.zeros((n,n),dtype=np.int32)
    for i in range(0, n-1): #don't let the last noe connect back to the first or get a cycle
        if forward_backwards[i] == 0:
            dag[i][i+1] = 1
        else:
            dag[i+1][i] = 1
    return dag

def plot_direct_numpy(dag, title):
    """
    plots a directed graph in numpy format
    input:
    matrx dag
    str title
    output:
    saves a pdf of an image of the dag
    """
    dag_nx = nx.DiGraph(dag)

    nx.draw(dag_nx, with_labels=True, font_weight='bold')
    plt.savefig('figures/' + title + '.pdf', bbox_inches='tight')
    plt.close()
    #TODO add formatting like titles and better readability
    return

def extract_undirected(cpdag, v):
    """
    given a cpdag and a node v, get all undirected edges out of v
    input:
    matrix cpdag
    node v
    output: 
    array containing all edges with which vhas an undirected edge with 
    """
    return np.flatnonzero(np.minimum(cpdag[v], 0))

def extract_all_directed(cpdag):
    """
    given a cpdag , extract all edges that are directed
    input:
    matrix cpdag
    output: 
    list of tuples of form (u, v) where u->v
    """
    n = cpdag.shape[0]
    edges = []
    for v in range(0, n):
        for u in range(0, n):
            if cpdag[v][u] == 1:
                edges.append((v, u))
    return edges


def chordal_random_intervention(cpdag, k):
    """
    generate a chordal random intervention of size up to k
    by chordal random we just mean intervene on nodes adjacentb to undirected edges
    input:
    matrix cpdag: the current cpdag
    int k: the number of perturbations
    output:
    list: the nodes we will perturb
    """

    #first extract all nodes with undirected edges next to them
    #do this by taking the min of each row (if there is a -1 we will get -1)
    #then select all the indices with a -1
    min_val = np.amin(cpdag, axis=1)
    possible_nodes = np.flatnonzero(np.minimum(min_val, 0)) #the min makes everthing -1 or 0

    #second randomly sample from the nodes we just extracted
    #even if you don't fill up the constraints (due to too much being identified
    #already),this is ok
    return np.random.choice(possible_nodes, size = min(k, np.size(possible_nodes)), replace = False)

def chordal_random_intervention_set(cpdag, n_b, k):
    """
    generates a batch of chordal random interventions
    input:
    matrix cpdag: current cpdag
    int n_b: interventions in the batch
    int k: max number of perturbations per intervention

    output:
    list of lists of ints intervention_set
    """
    intervention_set = []
    for _ in range(n_b):
        intervention = chordal_random_intervention(cpdag, k)
        intervention_set.append(intervention)
    return intervention_set

def meek(cpdag, new_edges=None, skip_r3=False, is_tree=False):
    """
    applies rules R1 to R4
    input:
    matrix cpdag
    list new_edges, the list of new edges that we start with for meek rules. None means use all directed edges
    bool skip_r3, if True does not consider r3. This can be used when working with interventions, since R3 is only
    used with colliders, and interventions don't uncover new colliders
    bool is_tree: if the mec inputted is a tree, means we need only do R1
    output:
    matrx cpdag
    """
    #keep going til there is a round where you find no edge
    edges_found = True
    latest_edges = new_edges
    if new_edges == None:
        latest_edges = extract_all_directed(cpdag)
    while edges_found:
        edges_found = False
        latest_edges_temp = []
        #for R1 just need to look at recently oriented edges (u, v) and orient all undirected 
        #(v, d) where there is not edge between d and u
        #print("R1 time")
        start_time = time.time()
        for edge in latest_edges:
            v = edge[1]
            u = edge[0]
            possible_orients = extract_undirected(cpdag, v)
            for d in possible_orients:
                #only orient if not yet oriented
                if cpdag[v][d] == -1:
                    #no edge to complete the triangle
                    if cpdag[d][u] == 0 and cpdag[u][d] == 0 and u!=d:
                        cpdag[v][d] = 1
                        cpdag[d][v] = 0
                        
                        edges_found = True
                        if((v,d)) not in latest_edges_temp:
                            latest_edges_temp.append((v, d))
        #for R2 look at recently oriented edges (u, v), check if any in a cycle pattern,
        #orient 
        if not is_tree:
            start_time = time.time()
            for edge in latest_edges:
                v = edge[1]
                u = edge[0]
                #now check all edges going into u
                nodes_into = np.flatnonzero(np.maximum(cpdag[:, u], 0))
                for w in nodes_into:
                    #if there exists w-v, orient it as w->v
                    if cpdag[w, v] == -1:
                        cpdag[w, v] = 1
                        cpdag[v, w] = 0
                        
                        edges_found = True
                        if((w,v)) not in latest_edges_temp:
                            latest_edges_temp.append((w, v))

                #now check all edges going out of v
                nodes_out = np.flatnonzero(np.maximum(cpdag[v], 0))
                for w in nodes_out:
                    #if there exists w-u, orient it as u->w
                    if cpdag[w, u] == -1:
                        cpdag[w, u] = 0
                        cpdag[u, w] = 1
                        
                        edges_found = True
                        if((u,w)) not in latest_edges_temp:
                            latest_edges_temp.append((u, w))
            #for R3 take any recently learnt edges and try to fit the pattern around it
            if not skip_r3:
                for edge in latest_edges:
                    v = edge[1]
                    u = edge[0]
                    #u is bottom left corner, v bottom right corner
                    #go over all colliders with it
                    nodes_collide_from = np.flatnonzero(np.maximum(cpdag[:, v], 0))
                    #w is toop right corner
                    for w in nodes_collide_from:
                        if w ==  u: #ignore the edge we already have
                            continue
                        #go over all possible diagonals
                        #t is top left node
                        for t in np.flatnonzero(np.minimum(cpdag[:, u], 0)):
                            #don't consider nodes already in the pattern
                            if t in [u, w, v]:
                                continue
                            #check if we get two triangles with new edges undirected
                            #also ensure the diagonal itself is= undirected
                            if (cpdag[t, u] == -1) and (cpdag[t, w] == -1) and (cpdag[t, v]==-1) and (cpdag[u, w] == 0) and (cpdag[w, u] == 0):
                                
                                cpdag[t, v] = 1 #direct the diagonal
                                cpdag[v, t] = 0
                                edges_found = True
                                if((t,v)) not in latest_edges_temp:
                                    latest_edges_temp.append((t, v))

            #for R4 go over the case of detecting each directed edge separately
            #left side directed considered first
            for edge in latest_edges:
                v = edge[1]
                u = edge[0]
                #find the bottom directed edge that starts at v
                nodes_out = np.flatnonzero(np.maximum(cpdag[v], 0))
                if len(nodes_out) == 0:
                    continue
                poss_diags_in = np.flatnonzero(np.maximum(cpdag[:, v], 0)).tolist()
                poss_diags_out = np.flatnonzero(np.maximum(cpdag[v], 0)).tolist()
                poss_diags_undirected = np.flatnonzero(np.minimum(cpdag[:, v], 0)).tolist()

                for w in nodes_out:
                    #now find all diagionals (exclude case of edges identified)
                    
                    #t is top right node
                    for t in (poss_diags_in + poss_diags_out + poss_diags_undirected):
                        if t in [u, w]:
                            continue
                        #check if the two undirected edges exist then orient the right one
                        if (cpdag[t, u] == -1) and (cpdag[t, w] == -1) and (cpdag[u, w] ==0) and (cpdag[w,u] == 0):
                            cpdag[t, w] = 1
                            cpdag[w, t] = 0
                            
                            edges_found = True
                            if((t,w)) not in latest_edges_temp:
                                latest_edges_temp.append((t, w))

            #now consider its the bottom side we directed. #TODO pull out repeated code in functions here
            
            for edge in latest_edges:
                v = edge[0]
                w = edge[1] #keep same names as for the code above

                nodes_in = np.flatnonzero(np.maximum(cpdag[:, v], 0))
                if len(nodes_in) == 0:
                    continue

                poss_diags_in = np.flatnonzero(np.maximum(cpdag[:, v], 0))
                poss_diags_out = np.flatnonzero(np.maximum(cpdag[v], 0))
                poss_diags_undirected = np.flatnonzero(np.minimum(cpdag[:, v], 0))
                for u in nodes_in:
                    #now everyting else is same as above
                    #now find all diagionals (exclude case of edges identified)
                    
                    #t is top right node
                    for t in (poss_diags_in.tolist() + poss_diags_out.tolist() + poss_diags_undirected.tolist()):
                        if t in [u, w]:
                            continue
                        #check if the two undirected edges exist then orient the right one
                        if (cpdag[t, u] == -1) and (cpdag[t, w] == -1) and (cpdag[u,w] == 0) and (cpdag[w,u] == 0):
                            cpdag[t, w] = 1
                            cpdag[w, t] = 0
                            edges_found = True
                            if((t,w)) not in latest_edges_temp:
                                latest_edges_temp.append((t, w))

        latest_edges = latest_edges_temp

    return cpdag

def orient_from_intervention(dag, cpdag, intervention_set, hard=True, is_tree=False):
    """
    uses the meek rules to update a cpdag given infinite sample interventional data 
    from a single intervention. currently no implementation of soft interventions. 
    input:
    matrix dag: the true dag
    matrix cpdag: the current cpdag
    list of lists of ints intervention_set: the nodes intervened on
    bool hard: whether we are doing hard interventions
    output:
    matrix: the cpdag after the intervention
    """

    #TODO: soft intervention capability

    n = dag.shape[0]
    new_edges = []
    for intervention in intervention_set:
        start_time = time.time()
        #first, orient all the edges we get from R0
        for v in intervention:
            for i in range(0, n):
                if i not in intervention:
                    #if its not an orientable edge, move on
                    if cpdag[v][i] != -1:
                        continue
                    cpdag[v][i] = dag[v][i]
                    cpdag[i][v] = dag[i][v]
                    if dag[v][i] == 1:
                        new_edges.append((v, i))
                    if dag[i][v] == 1:
                        new_edges.append((i, v))
    #second, extend the cpdag to a maximally oriented cpdag using the meek rules
    cpdag = meek(cpdag,new_edges, skip_r3 = False, is_tree=is_tree)
    return cpdag

def cpdag_from_dag_observational(dag):
    """
    given the true dag, returns the pcdag identified with just observational data

    input:
    matrix dag: the true dag

    output: 
    matrix: the maximally oriented cpdag given just observational data
    """

    n = dag.shape[0]

    #first need to get the skeleton of the dag
    skeleton = -dag - dag.T
    cpdag = skeleton

    #second we identify all unshielded colliders in the true dag

    #for all nodes
    for i in range(0,n):
        #iterate over pairs of parents j,k
        parents_i = np.flatnonzero(dag[:,i])
        for j,k in itertools.combinations(parents_i, r=2):   
            #if the parents are not adjacent we learn j->i and k->i
            if skeleton[j][k] == 0:
                cpdag[i][j] = 0
                cpdag[i][k] = 0
                cpdag[j][i] = 1
                cpdag[k][i] = 1

    #third we apply meek rules which are efficient in the observational setting
    cpdag = meek(cpdag)

    return cpdag

def cpdag_obj_val(cpdag, edgeorient=True):
    """
    computes the obj value of the cpdag. If edgeorient=True use the edge orienting objective
    input:
    matrix cpdag
    bool edgorient: whether to use the edgeorienting objective
    output:
    int: the objective value
    """

    return len(extract_all_directed(cpdag))

def orient_tree_root_v(cpdag, v):
    """
    orients a cpdag completely given the root. only true output for tree mecs: otherwise nonsense
    input:
    matrix cpdag
    int v: vertex to be the root
    output:
    matrix: a dag
    """
    n = cpdag.shape[0]
    #until we have oriented everything just go through applying R1
    oriented = [v] 
    while oriented != []:
        u = oriented.pop()
        for i in range(0, n):
            if cpdag[u][i] == -1:
                cpdag[u][i] = 1
                cpdag[i][u] = 0
                oriented.append(i)
    return cpdag

def objective_given_intervention(cpdag, intervention_set, ref_cpdag, n_samples = 1, max_score=1, is_tree=False):
    """
    compute the objective value of a specific intervention
    input:
    matrix: cpdag
    list of lists of ints intervention_set
    matrix ref_cpdag: the cpdag used in the obj to count the number of oriented edges
    in a tree.
    int n_samples: number of samples if mode is "sample"
    output:
    int: the objective value of that intervention
    """
    #sum over all dags in the equivalence class
    n = cpdag.shape[0]
    obj = 0

    if mode == "sample":
        for dag in mec_size.uniform_sample_dag_plural(cpdag, [], n_samples):
            cpdag2 = orient_from_intervention(dag, cpdag.copy(), intervention_set, is_tree=is_tree)
            obj += (cpdag_obj_val(cpdag2) - cpdag_obj_val(ref_cpdag))/n_samples
        return obj


    return obj/max_score

def objective_given_dags_interventions(cpdag, intervention_set, ref_cpdag, dag_list, is_tree=False):
    """
    objective_given_intervention but takes in a fixed list of dags to eval on
    """
    obj = 0
    for dag in dag_list:
        cpdag2 = orient_from_intervention(dag, cpdag.copy(), intervention_set, is_tree=is_tree)
        obj += (cpdag_obj_val(cpdag2) - cpdag_obj_val(ref_cpdag))/len(dag_list)
    return obj

def gen_stochastic_grad_fun(cpdag, ref_cpdag, num_sample=1, exact=True, total_x = 1, is_tree=False):
    #generates the gradient function for a bag of cpdags
    #uses the edge orienting obj
    n = cpdag.shape[0]
    def stochastic_grad(intervention_set, x):
        """
        sample one dag in the sum, compute the stochastic gradient as in karimi et al 2018
        (for the multilinear extension)
        input:
        matrix: cpdag
        list of lists of ints intervention_set- existing interventions
        matrix ref_cpdag: the cpdag used in the obj to count the number of oriented edges
        array of floats x: the point we are taking the gradient at
        int num_sample: the number of samples used to approximate the objective
        bool exact, True if use exact uniform sampling, but false if use the fast inexact method
        int total_x: for each dag, how many different interventions do we try
        output:
        int: the gradient of the objective
        """
        #print(cpdag)
        
        grad_f = np.zeros(n)
        #sample the intervention given x
        
        dags = mec_size.uniform_sample_dag_plural(cpdag, [], num_sample, exact=exact)
        for dag in dags:
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                x_rand = np.random.binomial(1, p = x)

                for v in range(0, n):
                    x_rand_upper = x_rand.copy()
                    x_rand_upper[v] = 1
                    x_rand_lower = x_rand.copy()
                    x_rand_lower[v] = 0

                    #tobytes allows us to store the numpy array
                    if x_rand_upper.tobytes() not in computed_val:
                        cpdag_upper = orient_from_intervention(dag, cpdag.copy(), intervention_set+[np.flatnonzero(x_rand_upper).tolist()], is_tree=is_tree)
                        cpdag_upper_score = cpdag_obj_val(cpdag_upper)
                        computed_val[x_rand_upper.tobytes()] = cpdag_upper_score
                    else:
                        cpdag_upper_score  = computed_val[x_rand_upper.tobytes()]

                    if x_rand_lower.tobytes() not in computed_val:
                        cpdag_lower = orient_from_intervention(dag, cpdag.copy(), intervention_set+[np.flatnonzero(x_rand_lower).tolist()], is_tree=is_tree)
                        cpdag_lower_score = cpdag_obj_val(cpdag_lower)
                        computed_val[x_rand_lower.tobytes()] = cpdag_lower_score
                    else:
                        cpdag_lower_score  = computed_val[x_rand_lower.tobytes()]

                    grad_f[v] += (cpdag_upper_score - cpdag_lower_score)/ (num_sample*total_x)

        return grad_f
    return stochastic_grad

def gen_ss_stochastic_grad_fun(cpdag, ref_cpdag, num_sample=1, exact=True, total_x = 1, is_tree=False):
    #same as gen_stochastic_grad_fun but ss is the groundset and we add interventions not perturbations
    #uses the edge orienting objective
    n = cpdag.shape[0]
    def stochastic_grad(x, ss):
        """
        sample one dag in the sum, compute the stochastic gradient as in karimi et al 2018
        (for the multilinear extension)
        input:
        matrix: cpdag
        matrix ref_cpdag: the cpdag used in the obj to count the number of oriented edges
        array of floats x: the point we are taking the gradient at
        int num_sample: the number of samples used to approximate the objective
        bool exact, True if use exact uniform sampling, but false if use the fast inexact method
        int total_x: for each dag, how many different interventions do we try
        output:
        int: the gradient of the objective
        """
        n_ss = len(ss)
        
        grad_f = np.zeros(n_ss)
        #sample the intervention given x
        
        dags = mec_size.uniform_sample_dag_plural(cpdag, [], num_sample, exact=exact)
        for dag in dags:
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                x_rand = np.random.binomial(1, p = x)

                for v in range(0, n_ss):
                    x_rand_upper = x_rand.copy()
                    x_rand_upper[v] = 1
                    x_rand_lower = x_rand.copy()
                    x_rand_lower[v] = 0

                    #tobytes allows us to store the numpy array in a hashable way
                    if x_rand_upper.tobytes() not in computed_val:
                        indices = np.flatnonzero(x_rand_upper).tolist()
                        interventions = [ss[i] for i in indices]
                        cpdag_upper = orient_from_intervention(dag, cpdag.copy(), interventions, is_tree=is_tree)
                        cpdag_upper_score = cpdag_obj_val(cpdag_upper)
                        computed_val[x_rand_upper.tobytes()] = cpdag_upper_score
                    else:
                        cpdag_upper_score  = computed_val[x_rand_upper.tobytes()]

                    if x_rand_lower.tobytes() not in computed_val:
                        indices = np.flatnonzero(x_rand_lower).tolist()
                        interventions = [ss[i] for i in indices]
                        cpdag_lower = orient_from_intervention(dag, cpdag.copy(), interventions, is_tree=is_tree)
                        cpdag_lower_score = cpdag_obj_val(cpdag_lower)
                        computed_val[x_rand_lower.tobytes()] = cpdag_lower_score
                    else:
                        cpdag_lower_score  = computed_val[x_rand_lower.tobytes()]

                    grad_f[v] += (cpdag_upper_score - cpdag_lower_score)/ (num_sample*total_x)

        return grad_f
    return stochastic_grad

def pipage(x, k):
    """
    perform pipage rounding for a nonmonotone submodular function
    "Maximizing a Monotone Submodular Function subject to a Matroid Constraint"
    in our case we don't necessarily start of with a tight solution but this is fine
    pipage round is performed on the set until 1 non integer value remains
    we then round this based on the better solution
    to start with we will also just randomly round the last value
    input:
    float array x: the solution to be rounded
    int k: constraint on perturbation size

    output:
    int list: the intervention
    """
    x = np.round(x, decimals=10) #round to 10 decimals for numerical stability

    #now select noninteger entries given by T as is the notation in the paper above
    T = np.flatnonzero((np.round(x, decimals=0) - x)).tolist()

    epsilon = 0.001 #rounding threshold for numerical stability
    while len(T) > 1:
        ij = np.random.choice(T, 2, replace=False)
        i = ij[0]
        j = ij[1]
        #option 1: x_i is the one where we make the i direction large
        dis_to_boundary_i = np.minimum(1-x[i], x[j])
        x_i = x.copy()
        x_i[i] += dis_to_boundary_i
        x_i[j] -= dis_to_boundary_i 

        #same for j

        dis_to_boundary_j = np.minimum(1-x[j], x[i])
        x_j = x.copy()
        x_j[i] -= dis_to_boundary_j
        x_j[j] += dis_to_boundary_j

        #sample the direction based on the sampling rule
        p = abs(dis_to_boundary_i / (dis_to_boundary_j + dis_to_boundary_i))
        if p>1+epsilon:
            print(x)
            print(p)
            print(x_i)
            print(x_j)
        assert p < 1 + epsilon #check that we don't have funky probabilities

        if p < 1+ epsilon and p > 1:
            p = 1
        if p > - epsilon and p < 0:
            p = 0
         
        change_lower = np.random.binomial(1, p, 1)[0]
        if change_lower:
            x = x_j
        else:
            x = x_i

        #change T if we get to some integer solutions
        if abs(x[i] - 1) < epsilon or abs(x[i]) < epsilon:
            x[i] = round(x[i])
            T.remove(i)
        if abs(x[j] - 1) < epsilon or abs(x[j]) < epsilon:
            x[j] = round(x[j])
            T.remove(j)

    #if one element left, bernoulli sample its value. can do since submod->concave along 
    #any nonnegative direction vector
    if len(T) == 1:
        #first just set to 0 if fulfilled condition and have rounding error
        if np.sum(x) > k and np.sum(x) < k+0.1:
            x[T[0]] = 0
        else:
            #if no interventions yet just do the intervention for sure
            if(np.sum(x) <= 1):
                x[T[0]] = 1
            #otherwise sample whether to include
            else:
                x[T[0]] = np.random.binomial(1, x[T[0]], 1)[0]

    #TODO: right now this is kind of bad since say we get[0.9, 0, 0], we can intervene on 
    #nothing. for now I've just done a hacky fix where if everything is 0 so far, we 
    #intervene on the last remaining variable for sure. thats in the if above
    return x

def gen_hess_fun(cpdag, ref_cpdag, num_sample=1, exact=True, total_x = 1, is_tree=False):
    """
    generates the hessian function of the edge orienting obj given a bag of cpdags
    num_sample: number of times we sample a dag
    total_x: number of repeats per sampled dag
    """
    n = cpdag.shape[0]
    def hess_fun(intervention_set, x, e):
        """
        estimates the hessian for gred
        """
        #sample the intervention given x
        
        dags = mec_size.uniform_sample_dag_plural(cpdag, [], num_sample, exact=exact)
        hess = np.zeros((n, n))
        for dag in dags:
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                S = []
                for s in range(n):
                    if e[s] < x[s]:
                        S.append(s)
                for i in range(n):
                    for j in range(i, n):
                        if i == j:
                            continue
                        S_ij = list({i, j}.union(set(S)))
                        S_i = list({i}.union(set(S)) - {j})
                        S_j = list({j}.union(set(S)) - {i})
                        S_minus = list(set(S) - {i,j}) #the set with both indices removed
                        for S_mod in [S_ij, S_i, S_j, S_minus]:
                            if np.array(S_mod).tobytes() not in computed_val:
                                cpdag_new = orient_from_intervention(dag, cpdag.copy(), intervention_set+[S_mod], is_tree=is_tree)
                                computed_val[np.array(S_mod).tobytes()] = cpdag_obj_val(cpdag_new)
                        
                        hess[i,j] += (computed_val[np.array(S_ij).tobytes()]-computed_val[np.array(S_i).tobytes()]-
                            computed_val[np.array(S_j).tobytes()]+computed_val[np.array(S_minus).tobytes()])/ (num_sample*total_x) 
            #print(time.time()-time2)
        return hess
    return hess_fun

def gen_ss_hess_fun(cpdag, ref_cpdag, num_sample=1, exact=True, total_x = 1, is_tree=False):
    """
    hessian for SS-based approach
    """
    n = cpdag.shape[0]
    def hess_fun(x, e, ss):
        """
        estimates the hessian for gred
        """
        n_ss=len(ss)
        
        #sample the intervention given x
        
        dags = mec_size.uniform_sample_dag_plural(cpdag, [], num_sample, exact=exact)
        hess = np.zeros((n_ss, n_ss))
        for dag in dags:
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                S = []
                for s in range(n_ss):
                    if e[s] < x[s]:
                        S.append(ss[s])
                for i in range(n_ss):
                    for j in range(i, n_ss):
                        if i == j:
                            continue
                        S_ij = list({tuple(a) for a in ([ss[i], ss[j]] + S)})
                        S_i = list({tuple(a) for a in ([ss[i]] + S)} - {tuple(ss[j])})
                        S_j = list({tuple(a) for a in ([ss[j]] + S)} - {tuple(ss[i])})
                        S_minus = list({tuple(a) for a in S} - {tuple(ss[j]), tuple(ss[i])}) #the set with both indices removed
                        for S_mod in [S_ij, S_i, S_j, S_minus]:
                            if np.array(S_mod).tobytes() not in computed_val:
                                cpdag_new = orient_from_intervention(dag, cpdag.copy(), S_mod, is_tree=is_tree)
                                computed_val[np.array(S_mod).tobytes()] = cpdag_obj_val(cpdag_new)
                        
                        hess[i,j] += (computed_val[np.array(S_ij).tobytes()]-computed_val[np.array(S_i).tobytes()]-
                            computed_val[np.array(S_j).tobytes()]+computed_val[np.array(S_minus).tobytes()])/ (num_sample*total_x) 
        return hess
    return hess_fun

def scdpp(cpdag, n_b, k, obj, stochastic_grad, hess_fun, T=100, max_score=1, M0 = 10, M=10, num_dag_sample=10, is_tree=False):
    """
    The improved version of stochastic coninuous greedy by Hassani et al 2020
    uses hessian approximation instead of just gradient information
    M0 and M are minibatch sizes
    """
    intervention_set = []
    n = cpdag.shape[0]

    u_bar = 1 #the upper bound for each variable in x_t
    A = np.vstack((np.ones(n), np.eye(n)))  #constraint matrix for linear program
    
    #gen_stochastic_grad_function needs num_x to be set to M
    for _ in range(n_b):
        #first lets do t=1
        x_t = np.zeros(n)
        x_tp = np.zeros(n) #previous x
        grad_f = np.zeros(n)
        for t in range(1, T):
            if t == 1:
                #sample minibatch and compute gradient g^0
                for i in range(M0):
                    grad_f += stochastic_grad(intervention_set, x_t) / M0
            else:
                hess = np.zeros((n,n))
                for i in range(M):
                    a = np.random.uniform()
                    e = np.random.uniform(size=n) 
                    x_a = a * x_t + (1-a) * x_tp
                    hess += hess_fun(intervention_set, x_a, e) / M
                delta = hess.dot(x_t - x_tp)
                grad_f = grad_f + delta
            #compute ascent direction
            b = np.insert(u_bar-x_t, 0, k) #constraint vector
            v_t = scipy.optimize.linprog(-grad_f, A_ub = A, b_ub = b, bounds = (0,1))
            x_tp = x_t
            x_t = x_t + v_t.x / T

        if(np.sum(x_t) > k+0.1):
            raise Exception
        #now do pipage rounding a few times and pick the best
        best_x = pipage(x_t, k) 
        best_score = obj(intervention_set+[np.flatnonzero(best_x).tolist()])
        #do ten runs of pipage rounding and pick the best
        for _ in range(10):
            x = pipage(x_t, k) 
            x_score = obj(intervention_set+[np.flatnonzero(x).tolist()])
            if x_score > best_score:
                best_x = x
                best_score = x_score
        intervention_set.append(np.flatnonzero(best_x).tolist())

    return intervention_set

def scdpp_ss(cpdag, n_b, k, obj, stochastic_grad, hess_fun, T=100, max_score=1, M0 = 10, M=10, num_dag_sample=10, is_tree=False, all_k = True, smart_ss=True):
    """
    The improved version of monotone stochastic coninuous greedy by Hassani et al 2020
    M0 and M are minibatch sizes. 
    With seperating system to select perturbations, so just use continuous approach
    to select interventions from SS. 
    """
    n = cpdag.shape[0]
    if smart_ss:
        ss = smart_ss_construct(cpdag, k) 
    else:
        #will only do it for the k given
        ss = ss_construct(n, k)
    n_ss = len(ss)
    #if we can completely identify using the seperating system, do so
    if n_ss <= n_b:
        return ss

    A = np.ones((1, n_ss))   #constraint matrix for linear program
    
    #gen_stochastic_grad_function needs num_x to be set to M
    #first lets do t=1
    x_t = np.zeros(n_ss)
    x_tp = np.zeros(n_ss) #previous x
    grad_f = np.zeros(n_ss)
    for t in range(1, T):
        if t == 1:
            #sample minibatch and compute gradient g^0
            for i in range(M0):
                grad_f += stochastic_grad(x_t, ss) / M0
        else:
            hess = np.zeros((n_ss,n_ss))
            for i in range(M):
                a = np.random.uniform()
                e = np.random.uniform(size=n_ss) 
                x_a = a * x_t + (1-a) * x_tp
                hess += hess_fun(x_a, e, ss) / M
            delta = hess.dot(x_t - x_tp)
            grad_f = grad_f + delta
        #compute ascent direction
        v_t = scipy.optimize.linprog(-grad_f, A_ub = A, b_ub = np.asarray([n_b]), bounds = (0,1))
        x_tp = x_t
        x_t = x_t + v_t.x / T

    #check x doesn't break the constraint
    if(np.sum(x_t) > n_b+0.1):
        raise Exception
    #resolve any slight numerical issues by ensuring the constraints are met
    x_t = np.minimum(x_t / np.linalg.norm(x_t, ord=1) * n_b, 1) 
    #now do pipage rounding a few times and pick the best
    best_x = pipage(x_t, n_b) 
    indices = np.flatnonzero(best_x).tolist()
    interventions = [ss[i] for i in indices]
    best_score = obj(interventions)
    #do ten runs of pipage rounding and pick the best
    for _ in range(10):
        x = pipage(x_t, n_b) 
        indices = np.flatnonzero(x).tolist()
        interventions = [ss[i] for i in indices]
        x_score = obj(interventions)
        if x_score > best_score:
            best_x = x
            best_score = x_score
    
    indices = np.flatnonzero(best_x).tolist()
    interventions = [ss[i] for i in indices]

    return interventions

def gred_intervention_set(n, n_b, k, obj, stochastic_grad, T=100, max_score=1, num_pipage_sample=10, is_tree=False, verbose=False):
    """
    generate an intervention set using our greedy method, that obeys the constraints
    of batch size b and max intervention size k for infinite samples per intervention
    only uses gradient information unlike scdpp, so is unused for the final experiments
    input:
    int n: number of nodes
    int n_b: batch size
    int k: max intervention size
    matrix ref_cpdag: the cpdag used in the obj to count the number of oriented edges
    int num_sample: the number of samples used to approximate the objective
    int T: number of iterations
    bool exact: True if use exact uniform sampling, False if use a fast sampler
    output:
    list of lists of ints: each list is an intervention on up to k nodes
    """

    intervention_set = []
    intervention = []

    for _ in range(n_b):
        x_t = np.zeros(n)
        d_t = np.zeros(n) #x_t
        u_bar = 1 #the upper bound for each variable in x_t
        A = np.vstack((np.ones(n), np.eye(n)))  #constraint matrix for linear program
        for t in range(0, T):
            
            rho_t = 4/(t+8)**(2/3)
            #we now compute an unbiased estimate of the gradient of the multilinear extension
            grad_f = stochastic_grad(intervention_set, x_t)

            d_t = (1-rho_t)*d_t + rho_t * grad_f
            #we now do a conditioning step which involves solving a linear program
            
            b = np.insert(u_bar-x_t, 0, k) #constraint vector
            v_t = scipy.optimize.linprog(-d_t, A_ub = A, b_ub = b, bounds = (0,1))
            x_t = x_t + v_t.x / T
            
            
            if t%20 == 0 and verbose:
                print("EVAL t=" + str(t))
                print(x_t)
                for _ in range(0, 5):
                    x = pipage(x_t, k) 
                    obj_val = obj(intervention_set+[np.flatnonzero(x).tolist()])
                    print(obj_val)
                print("==============")
            
            
            
        #check x doesn't break the constraint
        if(np.sum(x_t) > k+0.1):
            raise Exception
        #now do pipage rounding a few times and pick the best
        best_x = pipage(x_t, k) 
        best_score = obj(intervention_set+[np.flatnonzero(best_x).tolist()])
        #do ten runs of pipage rounding and pick the best
        for _ in range(10):
            x = pipage(x_t, k) 
            x_score = obj(intervention_set+[np.flatnonzero(x).tolist()])
            if x_score > best_score:
                best_x = x
                best_score = x_score
        intervention_set.append(np.flatnonzero(best_x).tolist())

    #TODO monotone case when you have soft interventions (very similar to this)
    return intervention_set

def ghassami_greedy(cpdag, n_b, ref_cpdag, num_sample):
    """
    the greedy approach of ghassami et al 2018 that only selects single interventions
    This doesn't implement lazy evaluation. 

    input:
    matrix cpdag
    int n_b: batch size
    matrix ref_cpdag: the cpdag used in the obj to count the number of oriented edges
    int num_sample: the number of samples used to approximate the objective
    output:
    list of lists of ints: each list is a singleton intervention
    """

    n = cpdag.shape[0]
    intervention_set = []
    intervention = []
    
    selected = []
    for _ in range(n_b):
        best_v = 0
        best_score = -np.inf
        #daglist for this round of intervention selection
        dag_list = mec_size.uniform_sample_dag_plural(cpdag, [], num_sample)
        for v in range(n):
            #if already selected just ignore it
            if v in selected:
                continue
            dummy_intervention_set = intervention_set + [[v]]
            temp_obj = objective_given_dags_interventions(cpdag, dummy_intervention_set, ref_cpdag, dag_list)
            if temp_obj > best_score:
                best_v = v
                best_score = temp_obj

        selected.append(best_v)
        intervention_set.append([best_v])

    return intervention_set

def edge_obj_sample(cpdags, ws, num_samples, obj=None, is_tree=False):
    """
    takes obj that uses a list of dags, and returns the obj with a fixed dag list
    cpdags is a list of MECs, ws is weights. We uniform sample from the possible DAGs
    If obj==None, assume is edge orienting
    """
    if obj in [objective_given_dags_interventions, None]:
        num_cpdags = len(cpdags)
        dag_list = []
        cpdag_list = []
        for i in range(num_samples):
            cpdag = cpdags[np.random.choice(num_cpdags, p=ws)]
            dag = mec_size.uniform_sample_dag_plural(cpdag, [], 1)[0]
            cpdag_list.append(cpdag)
            dag_list.append(dag)
        def new_obj(epsilon):
            out = 0
            for i in range(num_samples):
                out += objective_given_dags_interventions(cpdag_list[i], epsilon, cpdag_list[i].copy(), [dag_list[i]], is_tree=is_tree) / num_samples
            return out
        return new_obj
    return

def weighted_dags_edge_obj_sample(cpdags, ws, dags, obj = None, total_x=1, is_tree=False):
    """
    Just uses a list of given bootstrapped dags and corresponding cpdags and weights to 
    construct an objective that uses the same dist over dags as the finite sample obj
    also returns a way for us to get a stochastic gradients function
    
    total x is the number of samples of the intervention from
    the categorical dist given by x_t when computing the stochastic grad
    """
    n = cpdags[0].shape[0]
    num_samples = len(cpdags)
    def new_obj(epsilon):
        out = 0
        for i in range(num_samples):
            out += objective_given_dags_interventions(cpdags[i], epsilon, cpdags[i].copy(), [dags[i]], is_tree=is_tree) * ws[i]
        return out
    def new_stochastic_grad(intervention_set, x):
        """
        intervention set is existing interventions, x is the continuous numpy array
        """
        grad_f = np.zeros(n)
        #sample the intervention given x
        indexes = np.random.randint((len(dags)), size=1)
        
        for i in indexes:
            dag = dags[i]
            cpdag = cpdags[i]
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                x_rand = np.random.binomial(1, p = x)

                for v in range(0, n):
                    x_rand_upper = x_rand.copy()
                    x_rand_upper[v] = 1
                    x_rand_lower = x_rand.copy()
                    x_rand_lower[v] = 0

                    #tobytes allows us to store the numpy array
                    if x_rand_upper.tobytes() not in computed_val:
                        cpdag_upper_score = new_obj(intervention_set+[np.flatnonzero(x_rand_upper).tolist()])
                        computed_val[x_rand_upper.tobytes()] = cpdag_upper_score
                    else:
                        cpdag_upper_score  = computed_val[x_rand_upper.tobytes()]

                    if x_rand_lower.tobytes() not in computed_val:
                        cpdag_lower_score = new_obj(intervention_set+[np.flatnonzero(x_rand_lower).tolist()])
                        computed_val[x_rand_lower.tobytes()] = cpdag_lower_score
                    else:
                        cpdag_lower_score  = computed_val[x_rand_lower.tobytes()]

                    grad_f[v] += ws[i] * (cpdag_upper_score - cpdag_lower_score)/ (total_x* len(indexes))

        return grad_f
    
    def hess_fun(intervention_set, x, e):
        """
        estimates the hessian for gred
        """
        #print(cpdag)
        
        indexes = np.random.randint((len(dags)), size=1)
        #sample the intervention given x
        
        #print("stochastic grad inner")
        hess = np.zeros((n, n))
        for ind in indexes:
            dag = dags[ind]
            cpdag = cpdags[ind]
            #time2 = time.time()
            #print(time2-time1)
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                S = []
                for s in range(n):
                    if e[s] < x[s]:
                        S.append(s)
                for i in range(n):
                    for j in range(i, n):
                        if i == j:
                            continue
                        S_ij = list({i, j}.union(set(S)))
                        S_i = list({i}.union(set(S)) - {j})
                        S_j = list({j}.union(set(S)) - {i})
                        S_minus = list(set(S) - {i,j}) #the set with both indices removed
                        for S_mod in [S_ij, S_i, S_j, S_minus]:
                            if np.array(S_mod).tobytes() not in computed_val:
                                cpdag_new = orient_from_intervention(dag, cpdag.copy(), intervention_set+[S_mod], is_tree=is_tree)
                                computed_val[np.array(S_mod).tobytes()] = cpdag_obj_val(cpdag_new)
                        
                        hess[i,j] += ws[ind] * (computed_val[np.array(S_ij).tobytes()]-computed_val[np.array(S_i).tobytes()]-
                            computed_val[np.array(S_j).tobytes()]+computed_val[np.array(S_minus).tobytes()])/ (total_x* len(indexes)) 
            #print(time.time()-time2)
        return hess
    return new_obj, new_stochastic_grad, hess_fun

def weighted_dags_edge_obj_sample_ss(cpdags, ws, dags, obj = None, total_x=1, is_tree=False):
    """
    Just uses a list of given bootstrapped dags and corresponding cpdags and weights to 
    construct an objective that uses the same dist over dags as the finite sample obj
    also returns a way for us to get a stochastic gradients function

    Work with both finite and infinite sample objective
    
    total x is the number of samples of the intervention from
    the categorical dist given by x_t when computing the stochastic grad
    """
    num_samples = len(cpdags)
    n = cpdags[0].shape[0]

    def new_obj(epsilon):
        out = 0
        if obj == "MI":
            out += scipy.stats.entropy(ws, base=2)
            new_cpdags = []
            #print(cpdags)
            for i in range(num_samples):
                new_cpdags.append(orient_from_intervention(dags[i], cpdags[i].copy(), epsilon, is_tree=is_tree))
            #orient all the dags as if true_G is the true DAG
            #add on w* entropy of resulting distribution
            for i in range(num_samples):
                new_ws = ws.copy()
                for j in range(num_samples):
                    if j == i:
                        continue
                    if not np.array_equal(cpdags[i], cpdags[j]):
                        new_ws[j] = 0
                        continue
                    if not np.array_equal(new_cpdags[i], new_cpdags[j]):
                        new_ws[j] = 0
                out += - ws[i] * scipy.stats.entropy(new_ws, base=2)
        else:
            for i in range(num_samples):
                out += objective_given_dags_interventions(cpdags[i], epsilon, cpdags[i].copy(), [dags[i]], is_tree=is_tree) * ws[i]
        return out
    def new_stochastic_grad(x, ss):
        """
        intervention set is existing interventions, x is the continuous numpy array
        """
        
        #sample the intervention given x
        n_ss = len(ss)
        
        grad_f = np.zeros(n_ss)
        
        indexes = np.random.randint((len(dags)), size=1)
        #sample the intervention given x
        for ind in indexes:
            dag = dags[ind]
            cpdag = cpdags[ind]
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                x_rand = np.random.binomial(1, p = x)

                for v in range(0, n_ss):
                    x_rand_upper = x_rand.copy()
                    x_rand_upper[v] = 1
                    x_rand_lower = x_rand.copy()
                    x_rand_lower[v] = 0

                    #tobytes allows us to store the numpy array
                    if x_rand_upper.tobytes() not in computed_val:
                        indices = np.flatnonzero(x_rand_upper).tolist()
                        interventions = [ss[i] for i in indices]
                        cpdag_upper_score = objective_given_dags_interventions(cpdag, interventions, cpdag.copy(), [dag], is_tree=is_tree)
                        computed_val[x_rand_upper.tobytes()] = cpdag_upper_score
                    else:
                        cpdag_upper_score  = computed_val[x_rand_upper.tobytes()]

                    if x_rand_lower.tobytes() not in computed_val:
                        indices = np.flatnonzero(x_rand_lower).tolist()
                        interventions = [ss[i] for i in indices]
                        cpdag_lower_score = objective_given_dags_interventions(cpdag, interventions, cpdag.copy(), [dag], is_tree=is_tree)
                        computed_val[x_rand_lower.tobytes()] = cpdag_lower_score
                    else:
                        cpdag_lower_score  = computed_val[x_rand_lower.tobytes()]

                    grad_f[v] += ws[ind] * (cpdag_upper_score - cpdag_lower_score)/ (total_x * len(indexes))

        return grad_f

    def hess_fun(x, e, ss):
        """
        estimates the hessian for gred
        """
        n_ss=len(ss)
        
        grad_f = np.zeros(n)
        #sample the intervention given x
        
        hess = np.zeros((n_ss, n_ss))
        indexes = np.random.randint((len(dags)), size=1)
        #sample the intervention given x
        
        for ind in indexes:
            dag = dags[ind]
            cpdag = cpdags[ind]
            computed_val = {}
            #do runs for multiple different samples of x
            for _ in range(total_x):
                S = []
                for s in range(n_ss):
                    if e[s] < x[s]:
                        S.append(ss[s])
                for i in range(n_ss):
                    for j in range(i, n_ss):
                        if i == j:
                            continue
                        S_ij = list({tuple(a) for a in ([ss[i], ss[j]] + S)})
                        S_i = list({tuple(a) for a in ([ss[i]] + S)} - {tuple(ss[j])})
                        S_j = list({tuple(a) for a in ([ss[j]] + S)} - {tuple(ss[i])})
                        S_minus = list({tuple(a) for a in S} - {tuple(ss[j]), tuple(ss[i])}) #the set with both indices removed
                        for S_mod in [S_ij, S_i, S_j, S_minus]:
                            if np.array(S_mod).tobytes() not in computed_val:
                                cpdag_new = orient_from_intervention(dag, cpdag.copy(), S_mod, is_tree=is_tree)
                                computed_val[np.array(S_mod).tobytes()] = cpdag_obj_val(cpdag_new)
                        
                        hess[i,j] += ws[ind] * (computed_val[np.array(S_ij).tobytes()]-computed_val[np.array(S_i).tobytes()]-
                            computed_val[np.array(S_j).tobytes()]+computed_val[np.array(S_minus).tobytes()])/ (total_x * len(indexes)) 
        return hess
    return new_obj, new_stochastic_grad, hess_fun

def ss_construct(n, k):
    """
    given the size of the graph, constructs a separating system agnostic to the
    structure of the graph. Effectively implements theorem 1 in Shanmugam 2015
    input:
    int n
    int k
    output:
    list of list of ints separating system
    """

    #implement lemma 1 from paper
    a = math.ceil(n/k)
    l = math.ceil(math.log(n, a))
    #get distinct 'l' length labels for all elements 1:n, using letter from alphabet size 'a'+1
    #in every digit position any integer is used at most 'a' times

    #labels is n lists each with l elements
    labels = []
    #TODO: faster way to get a list of n empty lists

    x = l - 1
    for i in range(0, n):
        labels.append([])
    for d_ind in range(0, x+1):
        d = d_ind + 1

        p_d, r_d = divmod(n, (math.pow(a, d)))
        p_d1, r_d1 = divmod(n, (math.pow(a, d_ind)))

        #step one in the lemma
        count = 0
        num = 0
        while count < p_d * math.pow(a, d):
            #ensure we dopn't overflow the number to append
            amount_append = int(min(p_d * math.pow(a, d) - count, math.pow(a, d_ind)))
            for _ in range(amount_append):
                labels[count].append(num)
                count += 1
            num += 1
            if num > a-1:
                num = 0
        #step 2 in the lemma. bit unclear but i think it means go 0, 1, a-1 each r_d/a times
        num=0
        while count < n:
            amount_append = int(min(math.ceil(r_d/a), n - count))
            for _ in range(amount_append):
                labels[count].append(num)
                count+= 1
            num += 1

        #step 3 in the lemma
        for i in range(int(math.pow(a, d_ind)*p_d1), n):
            labels[i][-1] += 1 #increase last element of the list

    ss = []
    for i in range(1, l+1):
        for j in range(0, a):
            s_ij = []
            for label_ind in range(len(labels)):
                label = labels[label_ind]
                if label[i-1] == j:
                    s_ij.append(label_ind)
            ss.append(s_ij)

    return ss

def smart_ss_construct(cpdag, k):
    """
    takes in the cpdag, k, and returns a seperating system as 
    given in Lindgren et al. 18.
    for finding minimum vertex cover we use a greedy algorith,
    for finding an optimal coloring we use welch-powell
    """


    n = cpdag.shape[0]

    G = cpdag.copy()

    #convert the cpdag to a chordal graph
    #remove the directed edges
    for i in range(n):
        for j in range(i, n):
            if G[i][j] != G[j][i]:
                G[i][j] = 0
                G[j][i] = 0

    #now construct an approximately minimal vertex cover
    Gx = nx.DiGraph(G)
    S = vertex_cover.min_weighted_vertex_cover(Gx)
    #construct a coloring of the graph induced by the vertex cover
    Gs = nx.subgraph(Gx, S)

    coloring = nx.greedy_color(Gs, strategy='largest_first')

    #from each color, select intervention of size at most k
    def chunks(l, k):
        #chunks up a list l into pieces of size at most k
        assert k > 0
        return [l[i:i+k] for i in range(0, len(l), k)]
    
    interventions = []
    all_colors = set(coloring.values()) #set removes repeats
    for color in all_colors:
        l = [k for k,v in coloring.items() if v == color]
        interventions = interventions + chunks(l, k)

    return interventions

def ss_intervention(n, n_b, k, obj, cpdag, smart_ss = True, verbose=False):
    """
    greedily selects interventions from a seperating system
    input:
    n: number nodes in the true DAG
    int n_b: batch size
    int k: intervention size
    int num_sample: the number of samples used to approximate the objective
    function obj: an objective function. 
    matrix cpdag: 
    smart_ss bool: is True if using a graph specific ss constructor
    """

    best_interventions = []
    best_score = -np.inf
    #iterate over possible k and then pick the best at the end
    for k_cand in range(1, k+1):
        #first construct a separating system. we use Shanmugam 2015 which is agnostic
        #to the strucxture of the graph
        interventions = []
        if smart_ss:
            k_cand = k #skip all other possible k
            ss = smart_ss_construct(cpdag, k_cand)
        else:
            ss = ss_construct(n, k_cand)

        cur_obj = obj

        #for each element in the final batch choose greedily
        for i in range(n_b):
            current_obj_score = -np.inf
            best_intervention = []
            for intervention_cand in ss:
                interventions_cand = interventions + [intervention_cand]
                #TODO: you want a fixed set of graphs for all interventions
                cand_score = cur_obj(interventions_cand)
                if verbose:
                    print(interventions_cand)
                    print(cand_score)
                if cand_score > current_obj_score:
                    current_obj_score = cand_score
                    best_intervention = intervention_cand
            interventions.append(best_intervention)

        score = cur_obj(interventions)
        if verbose:
            print(interventions)
            print(score)
        #now greedily sample an intervention from it and save its obj if its better
        if score > best_score:
            best_score = score
            best_interventions = interventions
    #pick the intervention set with best score
    return best_interventions

def lazy_ss_intervention(n, n_b, k, obj, cpdag, smart_ss = True, all_k = True, verbose=False):
    """
    greedily selects interventions from a seperating system but uses lazy evaluation for speedup
    input:
    n: number nodes in the true DAG
    int n_b: batch size
    int k: intervention size
    int num_sample: the number of samples used to approximate the objective
    function obj: an objective function. 
    matrix cpdag: 
    smart_ss bool: is True if using a graph specific ss constructor
    bool all_k: if to try the SS for all or
    """

    #TODO: more sophisticated separating system construction

    best_interventions = []
    best_score = -np.inf
    #iterate over possible k and then pick the best at the end
    for k_cand in range(1, k+1):
        #first construct a separating system. we use Shanmugam 2015 which is agnostic
        #to the strucxture of the graph
        interventions = []
        if smart_ss:
            k_cand = k #skip all other possible k
            ss = smart_ss_construct(cpdag, k_cand)
        else:
            if not all_k:
                k_cand=k
            ss = ss_construct(n, k_cand)

        #return some random interventions if the separating system is empty
        if len(ss) == 0:
            return [np.random.randint(n, size=k).tolist() for _ in range(n_b)]

        cur_obj = obj

        delta_v = np.zeros(len(ss)) + np.inf #start initing at infty for the deltas

        current_batch_score = 0 #the score of the current batch

        #for each element in the final batch choose greedily
        for i in range(n_b):

            #sort delta_v from largest to smallest 

            best_intervention = []
            rel_improv = -np.inf
            #work from the current best intervention
            for j in np.flip(np.argsort(delta_v)):
                #print(j)
                intervention_cand = ss[j]
                #if you already have the intervention you can just skip it
                #removed this since in finite samples this isnt true
                """
                if intervention_cand in interventions:
                    delta_v[j] = -np.inf
                    continue
                """
                interventions_cand = interventions + [intervention_cand]
                
                #print(interventions_cand)
                cand_score = cur_obj(interventions_cand)
                #print(cand_score)

                rel_improv_j = cand_score - current_batch_score
                #print(rel_improv_j)
                if verbose:
                    print(interventions_cand)
                    print(cand_score)

                delta_v[j] = rel_improv_j 
                #if its better than everything else already, break

                #print(rel_improv_j)
                #print(delta_v)
                #print(j)
                if rel_improv_j >= np.max(delta_v):
                    break  
            
            #of the best interventions choose randomly
            if np.flatnonzero(delta_v == delta_v.max()).size == 0:
                print(delta_v)
                print(cand_score)
                print(ss)
                print(cur_obj(interventions_cand))
            best_intervention_index = np.random.choice(np.flatnonzero(delta_v == delta_v.max()))
            current_batch_score = delta_v[best_intervention_index] + current_batch_score

            interventions.append(ss[best_intervention_index])

        score = cur_obj(interventions)
        if verbose:
            print(interventions)
            print(score)
        #now greedily sample an intervention from it and save its obj if its better
        if score > best_score:
            best_score = score
            best_interventions = interventions
    #pick the intervention set with best score
    return best_interventions

def lazy_drg(n, n_b, k, obj, verbose=False):
    """
    An approach to gred_intervention_set that uses a fixed objective and the discrete
    random greedy akgorithm (https://theory.epfl.ch/moranfe/Publications/SODA2014.pdf)
    to select interventions
    """
    #take the k elements with the highest marginal improvement
    #sample from these uniformly
    best_interventions = []
    best_score = -np.inf
    
    interventions = []

    cur_obj = obj


    #for each element in the final batch choose greedily
    for i in range(n_b):

        #sort delta_v from largest to smallest 
        rel_improv = -np.inf

        #last 2k elements have dummy and contribute 0 at any point
        delta_v = np.zeros(n+2*k) + np.inf #start initing at infty for the deltas 

        current_batch_score = 0 #the score of the current batch
        intervention = []
        for _ in range(k):
            
            #work from the current best intervention
            num_updated = 0
            for j in np.flip(np.argsort(delta_v)):

                #if updated more than k do a lazy check
                if num_updated >= k:
                    #break if there are k options with better marginal improvement
                    if np.flip(np.argsort(delta_v)[k-1]) > delta_v[j]:
                        break

                if j in intervention:
                    cand_score = -np.inf
                if j >= n:
                    cand_score = current_batch_score #marginal cont of dummy vars is 0
                    num_updated+=1
                else:
                    interventions_cand = interventions + [intervention + [j]]
                    cand_score = cur_obj(interventions_cand)
                    num_updated+=1

                    if verbose:
                        print(interventions_cand)
                        print(cand_score)


                rel_improv_j = cand_score - current_batch_score

                
                delta_v[j] = rel_improv_j 
                #if its better than everything else already, break
                #once we have k elements better than the best previous gain we can stop
                
                
            #from the k best interventions sample uniformly
            best_intervention_index = np.flip(np.argsort(delta_v))[np.random.randint(0, k)]
            current_batch_score = delta_v[best_intervention_index] + current_batch_score

            if best_intervention_index < n: #only add if not a dummy variable
                intervention.append(best_intervention_index)
        interventions.append(intervention)

    score = cur_obj(interventions)
    if verbose:
        print(interventions)
        print(score)
    #pick the intervention set with best score
    return interventions

def ss_continuous_stochastic(n, n_b, k, obj, stochastic_grad, cpdag, T=100, max_score=1, num_pipage_sample=10, verbose=False):
    """
    Generates a seperating system then uses a continuous stochastic algorithm
    to optimize the monotone submodular function
    """

    ss = smart_ss_construct(cpdag, k) #use smart ss since the other requires rerunning for all different k
    n_ss = len(ss)
    #if we can completely identify using the seperating system, do so
    if n_ss <= n_b:
        return ss
    x_t = np.zeros(n_ss)
    d_t = np.zeros(n_ss) #x_t
    A = np.ones((1, n_ss))  #constraint matrix for linear program
    #start_time = time.time()
    for t in range(0, T):
        #print("TEST")
        
        rho_t = 4/(t+8)**(2/3)
        #we now compute an unbiased estimate of the gradient of the multilinear extension
        grad_f = stochastic_grad(x_t, ss) 

        d_t = (1-rho_t)*d_t + rho_t * grad_f
        #we now do a conditioning step which involves solving a linear program
        v_t = scipy.optimize.linprog(-d_t, A_ub = A, b_ub = np.asarray([n_b]), bounds = (0,1))
        x_t = x_t + v_t.x / T
        
        
        if t%20 == 0 and verbose:
            print("EVAL t=" + str(t))
            print(x_t)
            for _ in range(0, 1):
                x = pipage(x_t, n_b) 
                indices = np.flatnonzero(x).tolist()

                interventions = [ss[i] for i in indices]
                obj_val = obj(interventions)
            print(obj_val)
            print("==============")
        
        
        
    #check x doesn't break the constraint
    if(np.sum(x_t) > n_b+0.1):
        raise Exception
    #resolve any slight numerical issues by ensuring the constraints are met
    x_t = np.minimum(x_t / np.linalg.norm(x_t, ord=1) * n_b, 1) 
    #now do pipage rounding a few times and pick the best
    best_x = pipage(x_t, n_b) 
    indices = np.flatnonzero(best_x).tolist()
    interventions = [ss[i] for i in indices]
    best_score = obj(interventions)
    #do ten runs of pipage rounding and pick the best
    for _ in range(10):
        x = pipage(x_t, n_b) 
        indices = np.flatnonzero(x).tolist()
        interventions = [ss[i] for i in indices]
        x_score = obj(interventions)
        if x_score > best_score:
            best_x = x
            best_score = x_score
    
    indices = np.flatnonzero(best_x).tolist()
    interventions = [ss[i] for i in indices]

    return interventions

def process_ov(inter, b, k, OVs, obj, meth, k_range):
    """
    process experiment runs by feeding them into Ov list
    """
    f = "b=" + str(b) + '_k=' + str(k) + "_" + meth
    #for ss_a, might favour smaller seperating system if est objective is higher
    if meth in ['ss_a', 'ss_a_cont']:
        for kp in k_range:
            if kp < k:
                fp = "b=" + str(b) + '_k=' + str(kp) + "_" + meth
                if OVs[fp][-1] > obj:
                    obj = OVs[fp][-1]
    OVs[f].append(obj)
    return

def run_experiment(n, generator, meths, labs, k_range, title = '', name='', repeats=10):
    """
    runs experiments on chain graphs
    input:
    int n: number of nodes in chain
    str generator: a str saying what generator to use: 'chain', 'tree'...
    str title: the plot title
    str name: the plot filename
    int repeats: number of repetitions
    output:
    saves a plot of the results
    """ 

    #it doesn't really matter that we change the root since the objective and method
    #only see the MEC. it will matter when we do non-trees since can't sample whole mec
    fig = plt.figure()
    b_range = [1, 2, 3, 4, 5]
    plt.xticks(b_range)

    lines = ['-', '--', ':']
    invalid_list = []

    OVs = {}
    times_dict = {}

    for _ in range(repeats):
        valid_dag = False
        while valid_dag == False:
            random_root = np.random.choice(n)
            if generator == 'chain':
                dag = generate_chain_dag_fixed_root(n, random_root)
            elif generator == 'tree':
                dag = uniform_random_tree(n)
            elif generator == "bipartite":
                dag = ER_bipartite(int(n/2), n- int(n/2), 0.5)
            elif generator.startswith('ER'):
                #for erdos renyi write ER plus the param value
                rho = float(generator.split('_')[1])
                dag=generate_ER(n, rho)
            elif generator == "fully_connected":
                dag = generate_fully_connected(n)
            elif generator.startswith("barabasi_albert"):
                #for barabasi-albert append "_m" to the string
                m = generator.split('_')[2]
                dag = generate_barabasi_albert(n, m)
            elif generator == "kstar":
                dag = generate_k_star_system(n, max(k_range))
            elif generator.startswith("dream"):
                #read in the dream dag
                exp = int(generator.split("_")[1])
                cells = ["Ecoli1", "Ecoli2", "Yeast1", "Yeast2", "Yeast3"]
                f =  "gnw_obs/InSilicoSize50-" + cells[exp-1] + "_goldstandard_signed.tsv"
                dag = dream.load_true_dag(50, f)
            else:
                raise Exception
            cpdag = cpdag_from_dag_observational(dag)
            max_score = cpdag_obj_val(dag) - cpdag_obj_val(cpdag) # for normalizing scores
            #accept dags with mec size less than 100 and more than 5
            if generator.startswith("dream"):
                #no need to compute whole mec if in dream mode
                valid_dag=True
                break
            mec_size_total = mec_size.mec_size(cpdag, [])
            if generator not in ['fully_connected', 'chain', 'tree', 'kstar']:
                if n <= 20:
                    lower_const = 10
                else:
                    lower_const = 20
                if  mec_size_total <=100 and mec_size_total >= lower_const: 
                    valid_dag = True
                else:
                    invalid_list.append(1)
            else:
                valid_dag = True

        if not generator.startswith("dream"):
            full_mec = mec_size.enumerate_dags(cpdag, [])
        
        #print(objective_given_intervention(cpdag, [[0]], cpdag.copy()))

        num_samples = 40

        if generator in ["tree", "chain", "kstar"]:
            is_tree=True
        else:
            is_tree=False

        for k in k_range:
            for b in b_range:
                for i in range(len(meths)):
                    meth = meths[i]
                    f = "b=" + str(b) + '_k=' + str(k) + "_" + meth
                    if f not in OVs:
                        OVs[f] = []
                        times_dict[f] = []

                    #do one run of greedy on last round
                    if meth in ['ss_a', 'ss_b', 'cont', 'drg'] and b != b_range[-1]:
                        continue
                    start_time = time.perf_counter()
                    if meth == 'rand':
                        inter = chordal_random_intervention_set(cpdag, b, k)
                    elif meth == 'ss_a':
                        ss_obj = edge_obj_sample([cpdag], [1], num_samples, is_tree=is_tree) #use weights as 1 
                        inter = lazy_ss_intervention(cpdag.shape[0], b, k, ss_obj, cpdag, smart_ss=False, all_k=False)
                    elif meth == 'ss_b':
                        ss_obj = edge_obj_sample([cpdag], [1], num_samples, is_tree=is_tree) #use weights as 1 
                        inter = lazy_ss_intervention(cpdag.shape[0], b, k, ss_obj, cpdag, smart_ss=True)
                    elif meth == 'ss_a_cont':
                        ss_obj = edge_obj_sample([cpdag], [1], num_samples, is_tree=is_tree)
                        ss_stochastic_grad = gen_ss_stochastic_grad_fun(cpdag, cpdag.copy(), num_sample=1, exact=False, total_x = 1, is_tree=is_tree)
                        hess_fun = gen_ss_hess_fun(cpdag, cpdag.copy(), num_sample=1, exact=False, total_x = 1, is_tree=is_tree)
                        #run b times longer
                        inter = scdpp_ss(cpdag, b, k, ss_obj, ss_stochastic_grad, hess_fun, T=5*b, max_score=1, M0 = 5, M=5, smart_ss=False)
                    elif meth == 'ss_b_cont':
                        ss_obj = edge_obj_sample([cpdag], [1], num_samples, is_tree=is_tree)
                        ss_stochastic_grad = gen_ss_stochastic_grad_fun(cpdag, cpdag.copy(), num_sample=1, exact=False, total_x = 1, is_tree=is_tree)
                        hess_fun = gen_ss_hess_fun(cpdag, cpdag.copy(), num_sample=1, exact=False, total_x = 1, is_tree=is_tree)
                        #run b times longer
                        inter = scdpp_ss(cpdag, b, k, ss_obj, ss_stochastic_grad, hess_fun, T=5*b, max_score=1, M0 = 5, M=5, smart_ss=True)
                    elif meth == 'cont':
                        gred_obj = edge_obj_sample([cpdag], [1], num_samples, is_tree=is_tree)
                        gred_stochastic_grad = gen_stochastic_grad_fun(cpdag, cpdag.copy(), num_sample=1, exact=False, total_x = 1, is_tree=is_tree)
                        hess_fun = gen_hess_fun(cpdag, cpdag.copy(), num_sample=1, exact=False, total_x = 1, is_tree=is_tree)
                        inter = scdpp(cpdag, b, k, gred_obj, gred_stochastic_grad, hess_fun, T=5, max_score=1, M0 = 5, M=5)
                    elif meth == 'drg':
                        drg_obj = edge_obj_sample([cpdag], [1], num_samples, is_tree=is_tree)
                        inter=lazy_drg(n, b, k, drg_obj)
                    else:
                        #raise exception if no function for that method
                        raise Exception
                    #store objective and time
                    times_dict[f].append(time.perf_counter()-start_time)
                    if generator.startswith("dream"):
                        obj = objective_given_dags_interventions(cpdag, inter, cpdag.copy(), [dag], is_tree=is_tree)/ max_score
                    else:
                        obj = objective_given_dags_interventions(cpdag, inter, cpdag.copy(), full_mec, is_tree=is_tree)/ max_score
                    
                    if meth in ['ss_a', 'ss_b', 'cont', 'drg']:
                        for bp in b_range:
                            inter_p = inter[0:bp]
                            if generator.startswith("dream"):
                                obj_p = objective_given_dags_interventions(cpdag, inter_p, cpdag.copy(), [dag], is_tree=is_tree)/ max_score
                            else:
                                obj_p=objective_given_dags_interventions(cpdag, inter_p, cpdag.copy(), full_mec, is_tree=is_tree)/ max_score
                            process_ov(inter_p, bp, k, OVs, obj_p, meth, k_range)
                        continue

                    process_ov(inter, b, k, OVs, obj, meth, k_range)

    #save plot data in json
    with open(name +'_OVs.json', 'w') as fp:
        json.dump(OVs, fp)
    with open(name + '_times.json', 'w') as fp:
        json.dump(times_dict, fp)

    #list of invalid dag tallies
    with open(name + '_invalids.json', 'w') as fp:
        json.dump(invalid_list, fp)

    return

if __name__ == '__main__':

    #first command is run id
    if len(sys.argv) > 1:
        run = int(sys.argv[1])
        np.random.seed(run)
    else:
        run = 0
        np.random.seed(42)
    
    #generic infinite sample experiments
    for n in [10,20,40]:

        if n > 20:
            meths = ['rand', 'ss_a', 'ss_b', 'ss_a_cont', 'ss_b_cont', 'cont', 'drg']     
            labs = ['rand', 'ss_a', 'ss_b', 'ss_a_cont','ss_b_cont', 'cont', 'drg']
            k_range = [1, 2, 3, 4, 5]
        else:
            meths = ['rand', 'ss_a', 'ss_b', 'ss_a_cont', 'ss_b_cont', 'cont', 'drg']    
            labs = ['rand', 'ss_a', 'ss_b', 'ss_a_cont', 'ss_b_cont', 'cont', 'drg']
            k_range = [1, 2, 3]

        run_experiment(n, 'tree', meths, labs, k_range, title ="Mean Objective Value on Tree Graph n=" + str(n), name ='figures/tree_n=' + str(n)+ '_' + str(run), repeats=1)
        print("progress")

        if n in [10,20]:
            run_experiment(n, 'kstar', meths, labs, k_range, title ="Mean Objective Value on Star Forest Graph n=" + str(n), name ='figures/star_n=' + str(n)+ '_' + str(run), repeats=1)
            print("progress")
            
            run_experiment(n, 'ER_0.5', meths, labs, k_range, title ="Mean Objective Value on ER (rho=0.5) Graph n=" + str(n), name ='figures/ER_0.5_n=' + str(n)+ '_' + str(run), repeats=2)
            print("progress")

        run_experiment(n, 'ER_0.25', meths, labs, k_range, title ="Mean Objective Value on ER (rho=0.25) Graph n=" + str(n), name ='figures/ER_0.25_n=' + str(n)+ '_' + str(run), repeats=2)
        print("progress")

        run_experiment(n, 'ER_0.1', meths, labs, k_range, title ="Mean Objective Value on ER (rho=0.1) Graph n=" + str(n), name ='figures/ER_0.1_n=' + str(n)+ '_' + str(run), repeats=2)
        print("progress")
    
    #dream experiments
    k_range = [1,2,3,4,5]
    n=50
    meths = ['rand', 'ss_a', 'ss_b', 'cont']    
    labs = ['rand', 'ss_a', 'ss_b', 'cont']
    exp = (run%5) +1
    run_experiment(n, 'dream_'+str(exp), meths, labs, k_range, title ="Mean Objective Value on Dream Graph n=" + str(n), name ='figures_dream/dream_'+str(exp)+'_n=' + str(n)+ '_' + str(run), repeats=1)


    
    
