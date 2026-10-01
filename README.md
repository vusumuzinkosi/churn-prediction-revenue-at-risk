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
