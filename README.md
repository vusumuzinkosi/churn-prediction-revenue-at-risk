# Churn Prediction: Revenue at Risk

## 1. Business problem

**Client and context.** The imaginary client is a South African mobile network operator with a mix of prepaid and contract subscribers. Its customer retention department can take three actions on any customer they believe will churn: give them a call, a discount/bonus data offer, or an early upgrade offer. They are constrained by the number of contacts they can make: for this project I assume the team can contact about 300 customers per quarter.

**Question.** Which customers are most likely to churn in the next quarter, what will be the loss of revenue if no action is taken, and which of those customers should the retention department call first?

**Costs of being wrong.** The prediction model can be wrong in two ways, and both mistakes cost differently.

| Type of mistake | Consequences | Estimated cost |
|---|---|---|
| False Positive | Contacting a customer who would have stayed anyway | R140 (R40 for a call from an agent and R100 for the retention offer) |
| False Negative | Missing a customer who then churns | R3,000 (loss of a R250/month customer for 12 months) |

These costs are estimated values only. The exact figures will vary, but across any realistic range a missed churner costs far more than an unnecessary call, here roughly 20 times more.

**Metric and reasoning.** Because a false negative is significantly more expensive than a false positive, **recall** of the churners is the top target: how many of the customers who actually churned were caught by us? At the same time, calling every single customer gives perfect recall and makes the job impossible for the retention department. Therefore, precision is also measured alongside recall, the decision threshold is set based on the cost numbers rather than the default 0.5, and the final list of contacts is sorted by **expected loss** (product of the churn probability and the customer value). Accuracy is not used as the primary metric because in this case, the majority of customers do not churn, so predicting "no churn" for everyone would provide high accuracy while catching nobody.

**Data note.** The project is based on the Iranian Churn dataset (UCI id 563): 3,150 customers of an Iranian telecommunication company with usage and billing features in the first nine months and the churn status in month twelve. Its "Customer Value" variable is a value score calculated by the operator, not an amount in rand, so financial results are reported in the dataset's own value units; the rand amounts above are given for illustrative purposes only. In the South African setting, I would use the operator's actual usage and billing data: monthly spending, the end date of the contract, recharge data, complaints and network drops. All these data are governed by POPIA.

## 2. Data

**Source:** [Iranian Churn dataset](https://archive.ics.uci.edu/dataset/563/iranian+churn+dataset), UCI Machine Learning Repository, id 563 (CC BY 4.0). 3,150 rows, one per customer, from an Iranian telecom operator.

**Timing:** every feature is aggregated over the customer's **first 9 months**. `Churn` is their state at the **end of month 12**. The three months in between are the planning gap, which matches the business question: score customers at month 9, act before month 12.

| Column | Type | Meaning | Values |
|---|---|---|---|
| `call_failure` | count | Calls that failed during months 1 to 9 | 0 to 36 |
| `complains` | flag | Customer lodged a complaint | 0 = no, 1 = yes |
| `subscription_length` | months | How long the customer has been subscribed | 3 to 47 |
| `charge_amount` | ordinal | Spending band | 0 (lowest) to 10 (documented as 0 to 9; a few customers have 10) |
| `seconds_of_use` | seconds | Total call time | 0 to 17,090 |
| `frequency_of_use` | count | Number of calls made | 0 to 255 |
| `frequency_of_sms` | count | Number of text messages sent | 0 to 522 |
| `distinct_called_numbers` | count | Different numbers called | 0 to 97 |
| `age_group` | ordinal | Age band | 1 (youngest) to 5 (oldest) |
| `tariff_plan` | category | Type of service | 1 = pay as you go, 2 = contract |
| `status` | category | Activity status during months 1 to 9 | 1 = active, 2 = non-active |
| `age` | years | Customer age | 15 to 55 |
| `customer_value` | score | Value of the customer calculated by the operator (units not documented, not rand) | 0 to 2,165 |
| `churn` | target | Customer had left by month 12 | 0 = stayed, 1 = churned |

I renamed the original columns to `snake_case` (several had double spaces) and added a `customer_id` from the row number so every prediction can be traced back to the raw file.

**Is `status` leakage?** A feature leaks when it would not be known at the moment of prediction. `status` is documented as part of the 9-month aggregate, so the operator knows it at month 9: it is a legitimate early warning, not the answer in disguise. Non-active customers churn at 48%, against 6% for active ones. Because this rests on the documentation, Step 5 tests a model without it.

**Duplicates:** 300 rows (9.5%) are identical to another row in every column. With continuous values like seconds of use and customer value, that is almost certainly duplicated records rather than look-alike customers. Left in, a row and its copy could end up on both sides of the train/test split and inflate the test scores, so they are removed in Step 3.

## 3. What the data shows

After removing duplicates there are **2,850 customers**, of whom **446 churned (15.6%)**. A model that predicts "no churn" for everyone would already be 84% accurate, which is why accuracy is not the measure of success here.

![Churn rate by group](figures/churn_rate_by_group.png)

**Finding 1: complaints are the loudest warning sign.** Customers who complained churned at 83%, against 10% for those who did not. Non-active customers churned at 48% and pay-as-you-go customers at 17%, against 3% on contract.

![Usage of churners vs stayers](figures/usage_churners_vs_stayers.png)

**Finding 2: churners go quiet before they leave.** Over months 1 to 9, churners made about 40% as many calls, sent about 20% as many SMSs and called half as many distinct numbers as customers who stayed. The signal is visible three months before they leave.

![Customer value distribution](figures/customer_value_distribution.png)

**Finding 3: most churners are low-value, but the value lost is concentrated.** Churners hold only 4.4% of total customer value, yet the most valuable fifth of churners accounts for about half of all value lost to churn. A call list should weigh how much each customer is worth, not only how likely they are to leave. (Customer value is measured over months 1 to 9, while churners were already cutting back, so it probably understates what they were worth before.)

## 4. Baseline

The data is split 75/25 into training (2,137 customers) and test (713 customers), stratified so both have the same churn rate. The test set is not used until Step 6.

The baseline predicts "no churn" for everyone. On the test set it scores **84.3% accuracy, 0% recall and undefined precision**: it looks good and catches nobody. Every model has to beat it on recall and precision, not on accuracy.
