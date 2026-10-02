# Using FinApp

FinApp helps you organize the financial information you enter and examine a possible monthly plan. Start with practice values while learning the app. All amounts in one account should use the **same currency**; FinApp does not convert currencies or connect to a bank.

## A useful first run

1. **Create an account.** A fresh database has no example user or prefilled financial history.
2. **Enter gross monthly income** under **Profile → User details**. This is income before tax, used for the app's ratios.
3. **Save your financial profile.** Include monthly expenses, balances, loan information, the amount you can actually set aside each month, risk preference, and investment horizon where known.
4. **Open Dashboard.** Read the current recommendation, its supporting numbers, and its assumptions. Run analysis for the separate saved monthly allocation plan. Open **Advisor** for that plan and its agent findings.
5. **Add a goal**, such as a laptop with a target amount and date. Dashboard's current recommendation uses the new goal when you return. Run analysis again to update the saved allocation plan; older plans remain historical snapshots.
6. **Try a change.** Dashboard's scenario form previews one changed month without updating saved details. **Try a specific financial change** previews an income change, one-time cost, recurring discretionary cost reduction, extra loan payment, emergency savings deposit, or a changed goal savings budget. **Months** lets you save actual month-by-month figures and preview a plan from one recorded month.

After saving a Profile, open **Optional financial details** if you want to describe your income pattern, recurring expense categories, individual loans, or dated one-time costs. These entries are optional. The current Dashboard recommendation uses them when available. The saved Advisor allocation plan still uses the aggregate Profile values; the detail does not increase those totals. Use **Months** to record income you actually received, rather than treating an expected or guaranteed amount as observed history.
Dashboard's **Deeper financial analysis**, below the saved plan and financial picture, uses those saved entries to calculate gross cash flow, an emergency reserve gap, and a breakdown of income history, spending, goals, and upcoming costs. Each figure names its source. A blank figure means the necessary input is unknown; a partial category shows only the amount entered so far. The possible surplus is an upper bound from gross income before tax and unrecorded costs. The conservative income reference appears only after three consecutive recent recorded months and is a stress check, not a guaranteed future income.
The picture and current recommendation are read-only and do not change the saved Advisor allocation. Refreshing or editing these entries does not rewrite an older saved plan.
Leave an optional individual loan balance, loan payment, or amount reserved for an upcoming cost blank when you do not know it; blank means unknown, while zero means none.
Keep a cost already tracked as a Goal in Goals instead of also adding it as an upcoming one-time expense.

## What the fields mean

| Field | Enter this | Do not confuse it with |
| --- | --- | --- |
| **Gross monthly income** | Total income for a month before tax. | Take-home pay or a yearly amount. |
| **Monthly expenses** | Total monthly spending, **including debt payments**. | Only rent and utilities. |
| **Monthly savings contribution** | The amount you believe you can actually set aside from a month. The coordinator uses this as its allocation budget. | Your current savings balance or all income left after expenses. |
| **Savings balance** | Accessible savings you already have. | A monthly contribution. |
| **Emergency fund** | The part of accessible savings already reserved for unexpected needs. | Additional money on top of total savings. |
| **Outstanding debt balance** | Amount still owed. | This month's payment. |
| **Monthly debt payments** | Amount paid toward debt each month, already included in monthly expenses. | The full outstanding balance. |
| **Goal earmarked amount** | Money already set aside for that specific goal. | New monthly savings or emergency money to count twice. |
| **Guaranteed monthly income** | The part of your current gross monthly estimate that is actually assured, if known. | The lowest month observed or a promise of future earnings. |
| **Recurring expense detail** | A monthly cost already included in Profile's monthly expenses, excluding loan payments. | An extra cost to add on top of the Profile total. |
| **Loan detail** | A balance and payment already included in Profile's debt totals. | Additional debt or an additional monthly expense. |
| **Upcoming one-time expense** | A dated cost and any money reserved for it. | A recurring monthly bill or an automatic change to the current plan. |

If a monthly savings contribution is blank, the app can show findings but cannot produce a funded allocation. Zero means you know there is no new amount to allocate. Treat money left after entered spending as a ceiling: tax, payment timing, and costs you did not enter can reduce what is actually available.

## Reading a recommendation

Dashboard's **What should I do this month?** section ranks current actions from saved cash flow, dated costs, loan changes, recorded income, emergency reserve, and goal dates and priorities. It shows the reason, supporting calculations and their source, and assumptions for each action. Open the remaining actions to see the full list. The order can change after saved details change; no transfer or payment is made. Missing detail stays unknown, and the current gross surplus is only a ceiling before tax and unrecorded costs.

The separate saved monthly allocation plan follows this path:

```text
Your entered facts → financial checks → priority → proposed monthly action → reasons and limits
```

The six checks cover **Budget**, **Debt**, **Emergency fund**, **Goal planning**, **Risk assessment**, and **Investment readiness**. The coordinator brings them into one plan. Its current project rules give the emergency reserve priority, hold money unassigned when debt burden needs review, then consider active goals. Remaining money stays unassigned. These are educational rules, not guaranteed outcomes or instructions to move funds.

For example, suppose you enter monthly income of 60,000, expenses of 42,000 (including a 4,000 loan payment), a monthly savings contribution of 6,000, and an emergency fund of 12,000. Three months of entered expenses would be 126,000, leaving a 114,000 reserve gap under the app's rule. The plan would direct the **entered 6,000 monthly contribution** to that gap before a discretionary goal. It would not claim the whole 18,000 gross income-minus-expenses remainder is available or transfer 6,000 automatically. The actual Dashboard may show additional debt or goal considerations from the rest of your inputs.

Open **Advisor → Why this plan** and the agent findings to see the amounts and project rules behind a saved result. Editing an input does not rewrite an older analysis; run a new one to update the plan.

## Exploring changing income

**Dashboard scenario:** Enter a hypothetical month's gross income, expenses, and monthly savings amount. The **Try 20% less income** control starts from saved income; set income in Profile first. The comparison uses current saved balances, debt payments, and goals, but does not save the hypothetical month.

**Specific event preview:** Choose one event on Dashboard and enter its amount. For a subscription reduction, choose a discretionary recurring cost already entered in Profile. For an extra loan payment, choose a loan with a known remaining balance. For a goal contribution change, choose an active goal and enter a proposed monthly contribution; the comparison shows the current plan suggestion, the resulting gap to that goal's target, and whether the amount exceeds the saved total savings budget. It does not rebalance other goals. One-time costs include an optional amount already set aside and can be marked essential. They appear as obligations, not recurring monthly spending. An emergency savings deposit assumes new cash, not a transfer from existing savings. The comparison shows saved and hypothetical facts side by side, with separate one-time cash need and calculation limits. It changes no saved record, pays no loan, and moves no money.

**Months:** Record income received, total spending, essential bills, the loan payment due and actually paid, accessible savings, emergency reserve, and other relevant values for a particular month. A new month starts blank; copying the Profile is an explicit starting point. Enter at least two months to compare the lowest recorded income with the latest essential bills and scheduled loan payment. The recorded-month worksheet can subtract missing costs and cash you want to keep available before previewing a coordinated plan. That preview does not update your Profile or saved Advisor history. See [the detailed Months walkthrough](account-monthly-advice.md).

These are **what-if checks**, not forecasts. A low month in a short history does not establish the probability of another low month. If a recorded loan payment was missed or a bill went unfunded, the month planner blocks a new funded allocation and asks you to review that obligation.

## Product and research are separate

Normal Dashboard and saved Advisor plans use deterministic calculations and the rule-based coordinator. **Research** lets you inspect rule, random, and trained DQN agent selection, synthetic cases, model evidence, and proxy scores. An experimental method may omit a needed agent; the app labels that result as incomplete and withholds a full coordinated plan. A higher simulation score does not show that a person would save more or earn a better return. See [Research](research.md) for the experiment map.

Optional language-model features can help phrase captured results. The financial calculations, selected agents, and allocations remain structured. Check the displayed evidence before relying on generated wording.
