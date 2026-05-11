from pyomo.environ import SolverFactory, SolverStatus
from datetime import timedelta
import pandas as pd
import numpy as np
from param import *

import plotly.graph_objects as go
from plotly.subplots import make_subplots

def check_res(res):

    eps = 1e-3

    for t in range(len(res.t)):

        P_charge_bss = max(res.P_bss[t], 0)
        P_discharge_bss = max(-res.P_bss[t], 0)

        P_charge_ev = max(res.P_ev[t], 0)
        P_discharge_ev = max(-res.P_ev[t], 0)

        prod = (res.P_imp[t]+ 
               res.P_pv[t]+ res.P_gen[t]+ P_discharge_bss+ P_discharge_ev)
        cons = (res.P_exp[t]+ P_charge_bss+P_charge_ev+res.P_load[t] 
               + res.P_hp_hot[t]+ res.P_hp_cold[t])
        error = abs(prod - cons)
        if error >= eps:
            print(f"Error at t={t}, mismatch={error:.6f}")
    return

def print_res(res):
    # TODO: Make a function to print a summary of the results
    
    print("Objective value:", res.objective)#couts
    print("Import of the model:", sum(res.P_imp))#variables de décisions du model
    print("Export of the model:", sum(res.P_exp))#variables de décisions du model
    print("PV of the model:", sum(res.P_pv))#variables de décisions du model
    print("Generator production of the model:", sum(res.P_gen))#variables de décisions du model

    print("Total HP heating:", sum(res.P_hp_hot))#variables de décisions du model
    print("Total HP cooling:", sum(res.P_hp_cold))#variables de décisions du model

    
    print("Final battery SOC:", res.SOC_bss[-1])#etat final du model
    print("Final EV SOC:", res.SOC_ev[-1])#etat final du model
    return

def print_sizing_results(res):
    # TODO: Add a print with additional info specific to part 2
    print('Capacity of battery',res.C_bss )
    print('Power of battery',res.P_nom_bss)
    print('Capacity of pv',res.C_pv )
    print('Power of pv',res.P_nom_pv)
    print('Power of generator',res.P_nom_gen)
    print('Capacity of ev',res.C_ev )
    print('Power of ev',res.P_nom_ev)
    
    return



def plot_res(res):

    P_charge_bss = np.maximum(res.P_bss, 0)
    P_discharge_bss = np.maximum(-res.P_bss, 0)

    P_charge_ev = np.maximum(res.P_ev, 0)
    P_discharge_ev = np.maximum(-res.P_ev, 0)

    total_consumption = (res.P_load+P_charge_bss+P_charge_ev+res.P_hp_hot
        +res.P_hp_cold+res.P_exp)

    total_production = (res.P_imp+res.P_pv+res.P_gen+P_discharge_bss
        +P_discharge_ev)

    balance_error = total_production-total_consumption

    SOC_bss_percent = 100*res.SOC_bss/res.C_bss

    SOC_ev_percent = 100*res.SOC_ev/res.C_ev

    # cacher EV quand absent
    SOC_ev_percent = np.where(res.EV_connected == 1,SOC_ev_percent,np.nan)

    #  bilan énergétique
    fig1 = make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=0.08,
                         subplot_titles=("Energy flows","Energy balance residual"))

    # Flux principaux
    fig1.add_trace(go.Scatter(x=res.datetime,y=res.P_imp,name="Import"),row=1, col=1)

    fig1.add_trace(go.Scatter(x=res.datetime, y=res.P_exp,name="Export"),row=1, col=1)

    fig1.add_trace(go.Scatter( x=res.datetime,y=res.P_gen,name="Generator"),row=1, col=1)

    fig1.add_trace(go.Scatter(x=res.datetime,y=res.P_pv,name="PV"),row=1, col=1)

    fig1.add_trace(go.Scatter(x=res.datetime,y=total_consumption,name="Total consumption"),
        row=1, col=1)
    
    # Erreur de bilan
    fig1.add_trace(go.Scatter(x=res.datetime,y=balance_error,name="Balance error"),
        row=2, col=1)

    fig1.update_layout(title="Energy balance verification",height=800,
        xaxis2_title="Time",yaxis_title="Power [kW]",yaxis2_title="Residual [kW]",
        hovermode="x unified")

    fig1.show()


    fig2 = make_subplots(rows=2,cols=1,shared_xaxes=True,
        vertical_spacing=0.08,subplot_titles=("Power flows","SOC evolution"))


    fig2.add_trace(go.Scatter(x=res.datetime,y=res.P_imp,name="Import"),
        row=1, col=1)

    fig2.add_trace(go.Scatter(x=res.datetime,y=res.P_exp,name="Export"),
        row=1, col=1)

    fig2.add_trace(go.Scatter(x=res.datetime,y=res.P_gen,name="Generator"),
        row=1, col=1)
    
    fig2.add_trace(go.Scatter(x=res.datetime,y=res.P_pv,name="PV"),
        row=1, col=1)

    fig2.add_trace(go.Scatter(x=res.datetime,y=res.P_hp_hot,name="HP heating"),
        row=1, col=1)

    fig2.add_trace(go.Scatter(x=res.datetime,y=res.P_hp_cold,name="HP cooling"),
        row=1, col=1)

    # SOC batterie
    fig2.add_trace(go.Scatter(x=res.datetime,y=SOC_bss_percent,name="Battery SOC [%]"),
        row=2, col=1)

    # SOC EV
    fig2.add_trace(go.Scatter(x=res.datetime,y=SOC_ev_percent,name="EV SOC [%]"),
        row=2, col=1)

    fig2.update_layout(title="Microgrid operation",height=900,xaxis2_title="Time",
        yaxis_title="Power [kW]",yaxis2_title="SOC [%]",hovermode="x unified")

    fig2.show()
    fig1.write_html("energy_balance.html")
    fig2.write_html("microgrid_operation.html")

    return
def solve_model(m, res):
    # Solve the optimization problem
    solver = SolverFactory('gurobi')
    output = solver.solve(m, tee=True)  # Parameter 'tee=True' prints the solver output

    # Print elapsed time
    status = output.solver.status

    # Check the solution status
    if status == SolverStatus.ok:
        print("Simulation completed")
        res = save_results(res, m)
        res.save_sizing_results(m)
        return m, res
    elif status == SolverStatus.warning:
        print("Solver finished with a warning.")
    elif status == SolverStatus.error:
        print("Solver encountered an error and did not converge.")
    elif status == SolverStatus.aborted:
        print("Solver was aborted before completing the optimization.")
    else:
        print("Solver status unknown.")
    return None, None

def update_model(model, res, SOC_0_bss, SOC_0_ev, T_0_hp):
    for t in res.t:
        model.P_load[t] = res.P_load[t]
        model.P_pv_max[t] = res.P_pv_max[t]
        model.EV_connected[t] = res.EV_connected[t]
        model.t_arr[t] = res.t_arr[t]
        model.t_dep[t] = res.t_dep[t]
        model.SOC_i_ev[t] = res.SOC_i_ev[t]
        model.T_set[t] = res.T_set[t]
        model.P_loss[t] = res.P_loss[t]
    model.SOC_0_bss = SOC_0_bss
    model.SOC_0_ev = SOC_0_ev
    model.T_0_hp = T_0_hp

    return model

class Results:
    def __init__(self, start_time, n_days, yearly_kwh, yearly_km):
        self.start_time = start_time 
        self.t_s = int(n_days*24/delta_t)                # Total number of discrete time steps in the simulation
        self.n_days = n_days
        self.yearly_kwh = yearly_kwh
        self.yearly_km = yearly_km
        self.t = np.arange(0,self.t_s)

        self.P_pv = np.zeros(self.t_s)
        self.P_bss = np.zeros(self.t_s)
        self.P_ev = np.zeros(self.t_s)
        self.P_gen = np.zeros(self.t_s)
        self.P_imp = np.zeros(self.t_s)
        self.P_exp = np.zeros(self.t_s)

        self.SOC_ev = np.zeros(self.t_s)
        self.SOC_bss = np.zeros(self.t_s)

        # Initialize SOCs
        self.SOC_bss_i = 0.5          

        # Load data from CSV files into pandas DataFrames
        self.df = pd.read_csv('HW2.csv', delimiter=';', index_col="DateTime", parse_dates=True, date_format='%Y-%m-%d %H:%M:%S')#, date_parser=lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
        self.P_load = np.array([self.df.loc[self.start_time + timedelta(hours=t*delta_t)]["Load"].clip(min=0) * self.yearly_kwh for t in self.t])
        self.P_pv_max = np.array([self.df.loc[self.start_time + timedelta(hours=t*delta_t)]["PV"].clip(min=0) for t in self.t])
        self.EV_connected = np.array([self.df.loc[self.start_time + timedelta(hours=t*delta_t)]["EV"] for t in self.t])
        self.P_loss = np.array([self.df.loc[self.start_time + timedelta(hours=t*delta_t)]["P_loss"] for t in self.t])
        self.T_set = np.array([self.df.loc[self.start_time + timedelta(hours=t*delta_t)]["T_set"] for t in self.t])
        self.datetime = [self.start_time + timedelta(hours=t*delta_t) for t in self.t]


        self.SOC_i_ev = np.array([SOC_target_ev*C_ev - (self.EV_connected[t]*self.yearly_km) / (5e6) if self.EV_connected[t] > 0 and (t == 0 or self.EV_connected[t-1] == 0) else 0 for t in range(self.t_s)])
        self.t_arr = np.array([1 if self.EV_connected[t] > 0 and (t == 0 or self.EV_connected[t-1] == 0) else 0 for t in range(self.t_s)])
        self.t_dep = np.array([1 if self.EV_connected[t] == 0 and (t > 0 and self.EV_connected[t-1] > 0) else 0  for t in range(self.t_s)])
        if self.EV_connected[-1] > 0: self.t_dep[-1] = 1
        self.EV_connected = np.array([1 if self.EV_connected[t] > 0 else 0 for t in range(self.t_s)])

    def save_sizing_results(self, m):
        self.C_bss = m.C_bss.value
        self.P_nom_bss = m.P_nom_bss.value
        self.C_pv = m.C_pv.value
        self.P_nom_pv = m.P_nom_pv.value
        self.C_ev = m.C_ev.value
        self.P_nom_ev = m.P_nom_ev.value
        self.P_max_gen = m.P_max_gen.value


def save_results(res, m):
    res.P_imp = np.array([m.P_imp[t].value for t in m.periods])
    res.P_exp = np.array([m.P_exp[t].value for t in m.periods])
    res.P_pv = np.array([m.P_pv[t].value for t in m.periods])
    res.P_bss = np.array([m.P_charge_bss[t].value - m.P_discharge_bss[t].value for t in m.periods])
    res.P_ev = np.array([m.P_charge_ev[t].value - m.P_discharge_ev[t].value for t in m.periods])
    res.P_gen = np.array([m.P_gen[t].value for t in m.periods])
    res.P_hp_hot = np.array([m.P_hp_hot[t].value for t in m.periods])
    res.P_hp_cold = np.array([m.P_hp_cold[t].value for t in m.periods])
    res.T_hp = np.array([m.T_hp[t].value for t in m.periods])
    res.SOC_ev = np.array([m.SOC_ev[t].value for t in m.periods])
    res.SOC_bss = np.array([m.SOC_bss[t].value for t in m.periods])
    res.objective = m.objective()
    return res

def compute_year_costs(res):
    cost_import=np.sum(res.P_imp)*PI_imp*delta_t
    cost_export=np.sum(res.P_exp)*PI_exp*delta_t
    cost_gen=np.sum(res.P_gen)*PI_gen*delta_t

    opex=cost_import+cost_gen-cost_export

    print("cost of one year")
    print("Import cost:", cost_import)
    print("Export revenue:", cost_export)
    print("Generator cost:", cost_gen)
    print("OPEX:", opex)
    return 



