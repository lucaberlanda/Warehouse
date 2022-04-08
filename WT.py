import numpy as np
import pandas as pd
import os.path as pth
import matplotlib.pyplot as plt

filename = 'contracts_prices_light.csv'
filename_info = 'contracts_info.csv'
filepath = pth.join(pth.join('Other', 'WisdomTree'), filename)
filepath_info = pth.join(pth.join('Other', 'WisdomTree'), filename_info)


def plot_single_contract(df, code, m, y):
    single_contract = df[(df.contract_code == code) & (df.mat_month == m) & (df.mat_year == y)]
    single_contract.close.plot()
    plt.show()


# the current value of the contract is determined by multiplying the current price of a barrel of oil by the size
# of the contract. In this example, the current value would be $54 x 1000 = $54,000.

df = pd.read_csv(filepath).set_index('date')
df_info = pd.read_csv(filepath_info).set_index('contract_code')
print(df.contract_code.unique())

code = 'CL'

df = df[df.contract_code == code]
df.index = [pd.to_datetime(i, format='%d/%m/%Y') for i in df.index]
df = df.sort_index()
df = df.reset_index().sort_values(['index', 'mat_year', 'mat_month'],
                                  ascending=[True, False, False]).set_index('index')

plot_single_contract(df, code, 11, 2019)
quit()
df = df.merge(df_info, left_on='contract_code', right_index=True)

df['value_USD'] = df.close.mul(df.contract_size)
df['oi_USD'] = df.oi.mul(df.value_USD)
df['volume_USD'] = df.volume.mul(df.value_USD)

# todo n_months 12
roll_yield = df.reset_index().groupby(['index', 'contract_code'])['close'].pct_change().shift(-1) / 12
roll_yield.index = df.index
df['roll_yield'] = roll_yield

max_yield_by_dt = df.reset_index().groupby(['index', 'contract_code'])['roll_yield'].transform(max)
max_yield_by_dt.index = df.index
df.roll_yield == max_yield_by_dt
# todo first I compute the roll yield and then I filter
df_flt = df[(df.volume_USD > 100000000) & (df.oi_USD > 30000000)]


print()
