import os
import time
import numpy as np
import pandas as pd
from .functions import *
from .dp import dp_solver
from .cal_ce import cal_certainty_equi, generate_consumption_process
from .constants import *
import multiprocessing as mp
import itertools


def run_model(TERMrho, gamma, surv_prob, base_path, income_bf_ret, income_ret, sigma_perm, sigma_tran):

    TERM = int(TERMrho[0])
    rho = TERMrho[1]

    start = time.time()

    # get conditional survival probabilities
    cond_prob = surv_prob.loc[START_AGE:END_AGE - 1, 'CSP']  # 22:99
    cond_prob = cond_prob.values

    ###########################################################################
    #                  DP - generate consumption functions                    #
    ###########################################################################
    c_func_fp = os.path.join(base_path, 'results', f'c function_{TERM}_{rho:.2f}_{gamma}.xlsx')
    v_func_fp = os.path.join(base_path, 'results', f'v function_{TERM}_{rho:.2f}_{gamma}.xlsx')
    c_func_df, v_func_df = dp_solver(income_bf_ret, income_ret, sigma_perm, sigma_tran, cond_prob, TERM, rho, gamma)
    c_func_df.to_excel(c_func_fp)
    v_func_df.to_excel(v_func_fp)

    ###########################################################################
    #        CE - calculate consumption process & certainty equivalent        #
    ###########################################################################
    c_proc, _ = generate_consumption_process(income_bf_ret, sigma_perm, sigma_tran, c_func_df, TERM, rho)

    prob = surv_prob.loc[START_AGE:END_AGE, 'CSP'].cumprod().values

    c_ce, _ = cal_certainty_equi(prob, c_proc, gamma)

    print(f'########## Term: {TERM} | Rho: {rho:.2f} | Gamma: {gamma} | Exp_Frac: {gamma_exp_frac[gamma]} | CE: {c_ce:.2f} ##########')
    print(f"------ {time.time() - start} seconds ------")
    return TERM, rho, gamma, c_ce

def main(version, gamma_max, gamma_step):
    assert version=='ISA'
    start_time = time.time()

    ###########################################################################
    #                      Setup - file path & raw data                       #
    ###########################################################################
    # set file path
    income_fn = 'age_coefficients_and_var.xlsx'
    surviv_fn = 'Conditional Survival Prob Feb 16.xlsx'
    isa_fn = 'Loop on term and rho.xlsx'
    base_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    income_fp = os.path.join(base_path, 'data', income_fn)
    mortal_fp = os.path.join(base_path, 'data', surviv_fn)
    isa_fp = os.path.join(base_path, 'data', isa_fn)
    ce_fp = os.path.join(base_path, 'results', 'ce.xlsx')

    # read raw data
    age_coeff, std, surv_prob = read_input_data(income_fp, mortal_fp)


    ###########################################################################
    #              Setup - income process & std & survival prob               #
    ###########################################################################
    income_bf_ret = cal_income(age_coeff)
    income_ret = income_bf_ret[-1]

    # get std
    sigma_perm = std.loc['sigma_permanent', 'Labor Income Only'][education_level[AltDeg]]
    sigma_tran = std.loc['sigma_transitory', 'Labor Income Only'][education_level[AltDeg]]

    # read isa params
    isa_params = pd.read_excel(isa_fp)
    isa_params = isa_params[["Term", "1-rho"]].copy()
    isa_params = isa_params.loc[isa_params['1-rho'] > 0.5]
    # isa_params = isa_params[isa_params['Term']==15].copy()
    # isa_params = isa_params.iloc[7:9, :]
    gamma_arr = np.arange(1, gamma_max, gamma_step)
    fixed_args = [[x] for x in [surv_prob, base_path, income_bf_ret, income_ret, sigma_perm, sigma_tran]]

    search_args = list(itertools.product(isa_params.values, gamma_arr, *fixed_args))

    with mp.Pool(processes=mp.cpu_count()) as p:
        c_ce = p.starmap(run_model, search_args)

    c_ce_df = pd.DataFrame(c_ce, columns=['Term', 'Rho', 'Gamma', 'Consumption CE'])
    c_ce_df.to_excel(ce_fp)


    # Params check
    print("--- %s seconds ---" % (time.time() - start_time))
    print('AltDeg: ', AltDeg)
    print('permanent shock: ', sigma_perm)
    print('transitory shock: ', sigma_tran)
    print('lambda: ', ret_frac[AltDeg])
    print('theta: ',  unemp_frac[AltDeg])
    print('pi: ', unempl_rate[AltDeg])
    print('W0: ', INIT_WEALTH)

