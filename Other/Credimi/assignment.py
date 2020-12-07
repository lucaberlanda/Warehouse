# CREDIMI CHALLENGE
# Model for offering the best possible interest rate (i.e. maximizing the probability of being accepted) gived
# a total portfolio yield of 3.5%

import numpy as np
import collections
import pandas as pd
import seaborn as sns
import scipy.stats as ss
import matplotlib.pyplot as plt

from sklearn.metrics import accuracy_score
from sklearn.metrics import confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

sns.set_style('white')
df_raw = pd.read_excel('futuro_applications_dataset.xlsx', sheet_name='dataset')
plot_int_vs_rating = False
get_spearman = False

aggregations = {'applicationDate': 'count', 'Interest Rate Proposed': 'median', 'fdgRating': 'mean'}

# DATA CLEANING
df_raw.columns = df_raw.iloc[0, :]
df_raw = df_raw.drop(0)
cmp_list = df_raw.loc[:, 'Company ID'].values.tolist()
cmp_doubles = [item for item, count in collections.Counter(cmp_list).items() if count > 1]
df_raw = df_raw.set_index('Company ID')

for cmp in cmp_doubles:
    df_raw = df_raw.drop(cmp)

for i in df_raw.columns:
    df_raw = df_raw.replace({i: {'inf': np.nan}})

# dictionary to map credimi rating; since we will be using a Gradient Boosting /  Random Forest, we can overlook
# the non-linearity in the rating definition, hence assigning a range from 0 to 10
credimi_rating_mapping = {'A3': 1, 'A4': 2, 'B1': 3, 'B2': 4, 'B3': 5, 'B4': 6, 'C1': 7, 'C2': 8, 'C3': 9, 'C4': 10}
df_raw = df_raw.replace({'Credimi algoRating': credimi_rating_mapping})

# one hot encoding for Company Geo Area, ignore cities and region, prone to overfitting.
df_raw = pd.concat([df_raw, pd.get_dummies(df_raw.loc[:, 'Company Geo Area'])], axis=1)

y_mapping_dict_str = {'AcceptedByTheClient': 'Accepted',
                      'Financed': 'Accepted',
                      'ReadyForApproval': 'Accepted',
                      'Uninterested': 'Refused'}

y_mapping_dict = {'Accepted': 1,
                  'Refused': 0}

do_drop = ['Rejected']
df_approved = df_raw[df_raw.dossierStatus != 'Rejected']
df_tba = df_approved[df_approved.dossierStatus == 'ApprovedByCredimi']
df_answered = df_approved[df_approved.dossierStatus.isin(list(y_mapping_dict_str.keys()))]
df_answered = df_answered.replace({'dossierStatus': y_mapping_dict_str})

# Box Whisker Plot with Interest Rate ?
if plot_int_vs_rating:
    # PLOT INTEREST RATE VS RATING
    interest_vs_rating = df_answered.loc[:, ['Interest Rate Proposed', 'Credimi algoRating', 'dossierStatus']].dropna()
    fig = plt.figure(1, figsize=(11, 6))
    ax = fig.add_subplot(111)
    acc_labels = list(set(y_mapping_dict_str.values()))
    for acc_label in acc_labels:
        to_plot = interest_vs_rating[interest_vs_rating.dossierStatus == acc_label]
        ax.scatter(to_plot.loc[:, 'Interest Rate Proposed'], to_plot.loc[:, 'Credimi algoRating'], s=50, alpha=0.5)

    ax.legend(acc_labels)
    ax.set_xlabel('Interest Rate', size=13)
    ax.set_ylabel('Algo Rating', size=13)
    ax.set_title('Interest Rate vs Rating', size=20)
    plt.tight_layout()
    plt.show()

to_drop_cols = ['applicationDate', 'Credit Decision Outcome', 'approvedAt', 'ATECO Identifier', 'Company City',
                'Company Province', 'Company Geo Area', 'Company Region', 'Company ZIP Code', 'Juridicial Form',
                'ATECO', 'Credimi Industry', 'Company Start Date', 'cr_date_eoy', 'last_available_cr_date']

df_answered = df_answered.replace({'dossierStatus': y_mapping_dict}).drop(to_drop_cols, axis=1)
df_answered = df_answered.dropna(how='all', axis=1).fillna(df_answered.mean())

# seems reasonable to assume that the interest rate proposed would be lower than the one originally proposed
labels = df_answered.loc[:, 'dossierStatus']
features = df_answered.drop('dossierStatus', axis=1)
features_refusals = features.loc[labels[labels == 0].index, :]
features_labels = features.columns.tolist()

# compute SPEARMAN CORRELATION to get better how credit algo works
if get_spearman:
    spearman_dict = {}
    for i in features.columns:
        sp_corr = ss.spearmanr(pd.concat([features.loc[:, i], features.loc[:, 'Interest Rate Proposed']], axis=1))[0]
        print(sp_corr)
        spearman_dict[i] = sp_corr

    print(pd.Series(spearman_dict).sort_values(ascending=False))

X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.4)
# clf = RandomForestClassifier(n_estimators=500, max_depth=5)
clf = GradientBoostingClassifier(n_estimators=10000,
                                 min_samples_split=5,
                                 min_samples_leaf=5)
clf.fit(X_train, y_train)
clf_predict = clf.predict(X_test)

feature_imp = pd.Series(clf.feature_importances_, index=features_labels).sort_values()
# pd.Series(clf.feature_importances, index=relevant_columns).sort_values(ascending=False).plot(kind='bar', color='blue')

print(accuracy_score(y_test, clf_predict))
print(confusion_matrix(y_test, clf_predict))

new_comp_ptf = {}
for comp in features_refusals.index:
    comp_info = {}
    pred = {}
    ratio = {}
    old_acc_proba = 1
    original_int_rate = features_refusals.loc[comp, 'Interest Rate Proposed']
    for i in np.arange(1, 10.5, 0.5):
        features_refusals.loc[comp, 'Interest Rate Proposed'] = i
        acceptance_proba = clf.predict_proba(features_refusals.loc[comp, :].values.reshape(1, -1))[0][1]
        # make probability monotonous in order to avoid counter-intuitive behaviours
        if acceptance_proba > old_acc_proba:
            acceptance_proba = old_acc_proba

        pred[i] = acceptance_proba
        old_acc_proba = acceptance_proba

    pred_s = pd.Series(pred)
    proposed_int = max(pred_s[pred_s == max(pred_s)].index)

    comp_info['proposed_interest_plus_0bp'] = proposed_int
    comp_info['proposed_interest_plus_50bp'] = min(proposed_int + 0.5, 10)
    comp_info['proposed_interest_plus_100bp'] = min(proposed_int + 1, 10)
    comp_info['proposed_interest_plus_150bp'] = min(proposed_int + 1.5, 10)

    comp_info['acceptance_prob_plus_0bp'] = round(max(pred_s), 3)
    comp_info['acceptance_prob_plus_50bp'] = pred_s.loc[min(proposed_int + 0.5, 10)]
    comp_info['acceptance_prob_plus_100bp'] = pred_s.loc[min(proposed_int + 1, 10)]
    comp_info['acceptance_prob_plus_150bp'] = pred_s.loc[min(proposed_int + 1.5, 10)]

    comp_info['amount'] = features_refusals.loc[comp, 'amountProposed (€)']
    comp_info['old_interest'] = original_int_rate
    new_comp_ptf[comp] = comp_info

fig = plt.figure(1, figsize=(11, 6))
ax2 = fig.add_subplot(211)
ax3 = fig.add_subplot(212)
probs_db = pd.DataFrame(new_comp_ptf).T
bp_diff = [0, 50, 100, 150]
for i in bp_diff:
    aa = probs_db.loc[:, ['amount', 'old_interest', 'proposed_interest_plus_%sbp' % str(i),
                          'acceptance_prob_plus_%sbp' % str(i)]]

    aa['int_diff'] = aa.loc[:, 'old_interest'] - aa.loc[:, 'proposed_interest_plus_%sbp' % str(i)]
    to_propose = aa[aa.int_diff > 0]
    acceptance_dict = {}
    for comp in to_propose.index:
        prob = to_propose.loc[comp, 'acceptance_prob_plus_%sbp' % str(i)]
        choice = np.random.choice([1, 0], size=100, p=[prob, 1 - prob])
        acceptance_dict[comp] = pd.Series(choice)

    new_ptfs_dict = {}
    acceptance_df = pd.DataFrame(acceptance_dict)
    for sim in acceptance_df.index:
        new_ptf_dict = {}
        scenario = acceptance_df.loc[sim, :]
        acc_in_sim = scenario[scenario == 1]
        new_accepted = to_propose.loc[acc_in_sim.index, :]

        new_ptf_size = new_accepted.amount.sum()
        new_clients = len(new_accepted.index)
        new_accepted['amount_pct'] = new_accepted.amount / new_ptf_size
        new_ptf_yield = new_accepted.loc[:, 'amount_pct'].\
            dot(new_accepted.loc[:, 'proposed_interest_plus_%sbp' % str(i)])

        new_ptf_dict['yield'] = new_ptf_yield
        new_ptf_dict['amount'] = new_ptf_size
        new_ptf_dict['new_clients'] = new_clients
        new_ptfs_dict[sim] = new_ptf_dict

    new_ptf_df = pd.DataFrame(new_ptfs_dict).T

    ax2.scatter(new_ptf_df.loc[:, 'new_clients'],
                new_ptf_df.loc[:, 'yield'], s=50, alpha=0.5)

    ax3.scatter(new_ptf_df.loc[:, 'amount'],
                new_ptf_df.loc[:, 'yield'], s=50, alpha=0.5)

    ax2.legend(bp_diff)
    ax3.legend(bp_diff)

plt.show()

aggregations_funnel = {'applicationDate': 'count', 'Interest Rate Proposed': 'median', 'fdgRating': 'mean'}
df_raw.groupby('dossierStatus').agg(aggregations_funnel)
df_raw.loc[:, u'requestedAmount (€)'] = df_raw.loc[:, u'requestedAmount (€)'].fillna(0)
df_raw.loc[:, u'amountProposed (€)'] = df_raw.loc[:, u'amountProposed (€)'].fillna(0)
df_raw['amount_prop_vs_req'] = df_raw.loc[:, u'amountProposed (€)'] / df_raw.loc[:, u'requestedAmount (€)'] -1
size_risk = df_raw.groupby(['dossierStatus', 'Credimi algoRating']) # , pd.cut(df.views, bins)])
aggregations_size_risk = {u'requestedAmount (€)': 'median', u'amountProposed (€)': 'median', 'amount_prop_vs_req': 'median'}
size_risk.agg(aggregations_size_risk)
bins = 10
size_risk = df_raw.groupby(['dossierStatus', pd.cut(df_raw.loc[:,u"Fatturato (€'000)"], bins)])
aggregations_size_risk = {u'requestedAmount (€)': 'median', u'amountProposed (€)': 'median', 'amount_prop_vs_req': 'median'}
size_risk.agg(aggregations_size_risk)


def propose_optimal_interest_rate(cmp_info):
    old_acc_proba = 1
    original_int_rate = cmp_info.loc['Interest Rate Proposed']

    for i in np.arange(1, 10.5, 0.5):
        cmp_info.loc['Interest Rate Proposed'] = i
        acceptance_proba = clf.predict_proba(cmp_info.values.reshape(1, -1))[0][1]
        # make probability monotonous in order to avoid counter-intuitive behaviours
        if acceptance_proba > old_acc_proba:
            acceptance_proba = old_acc_proba

        pred[i] = acceptance_proba
        old_acc_proba = acceptance_proba

    pred_s = pd.Series(pred)
    proposed_int = max(pred_s[pred_s == max(pred_s)].index)
    return proposed_int, pred_s


new_comp_ptf = {}
for comp in features_refusals.index:
    comp_info = {}
    pred = {}
    ratio = {}

    # optimal interest and range
    optimal_int, int_curve = propose_optimal_interest_rate(features_refusals.loc[comp, :])

    comp_info['proposed_interest_plus_0bp'] = optimal_int
    comp_info['proposed_interest_plus_50bp'] = min(optimal_int + 0.5, 10)
    comp_info['proposed_interest_plus_100bp'] = min(optimal_int + 1, 10)
    comp_info['proposed_interest_plus_150bp'] = min(optimal_int + 1.5, 10)

    comp_info['acceptance_prob_plus_0bp'] = round(max(int_curve), 3)
    comp_info['acceptance_prob_plus_50bp'] = pred_s.loc[min(int_curve + 0.5, 10)]
    comp_info['acceptance_prob_plus_100bp'] = pred_s.loc[min(int_curve + 1, 10)]
    comp_info['acceptance_prob_plus_150bp'] = pred_s.loc[min(int_curve + 1.5, 10)]

    comp_info['amount'] = features_refusals.loc[comp, u'amountProposed (€)']
    comp_info['old_interest'] = original_int_rate
    new_comp_ptf[comp] = comp_info