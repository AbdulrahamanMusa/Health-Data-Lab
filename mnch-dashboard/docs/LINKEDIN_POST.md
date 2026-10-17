# LinkedIn post

Attach `media/dhis2-interoperability-linkedin.mp4` (3:39) with `media/linkedin-thumbnail.png`
as the cover. Replace the link if the blog post URL changes.

---

**From dashboards to risk prediction: one DHIS2 source, two ways to support decisions**

A few months ago I connected DHIS2 to Power BI. Live from the DHIS2 Web API, the dashboard shows
antenatal care, immunisation and reporting against targets, by district and chiefdom, with written
findings and recommended actions. It answers a key question for any health programme:
*what has happened, and where?*

This time I asked a second question: *where might problems arise next?*

I rebuilt the same dashboard in Shiny for Python (with a React interface), using the same DHIS2
queries and the same measures. Its numbers match the Power BI report exactly. Then I added a
facility risk forecast:

🔹 A logistic regression uses each facility's last 3 to 6 months of DHIS2 data
🔹 It estimates the probability of two outcomes next quarter: Penta 3 coverage below 70%, and ANC 1 to 4 dropout above 50%
🔹 Every estimate shows the reasons behind it
🔹 Tested on a quarter it had not seen, against the simple rule "same as last quarter": better for vaccination coverage (AUC 0.82 vs 0.79), about the same for antenatal care (0.85 vs 0.86)

The two approaches complement each other: descriptive dashboards help us understand performance;
carefully validated risk estimates can help decide where to look first.

🎬 The video shows both applications side by side.
📖 The full project story, architecture and lessons learned: https://am-datasolution.com/posts/dhis2-interoperability-power-bi-shiny/

⚠️ For education and demonstration only. The data come from the public DHIS2 demo database
(Sierra Leone) and are not evidence of real facility performance. The model illustrates an
approach; it is not a validated decision-making system.

I'd love your feedback, especially from DHIS2 implementers and M&E colleagues: which indicators
would you want a risk estimate for?

#DHIS2 #PublicHealth #HealthInformationSystems #Interoperability #PowerBI #Python #Shiny #DataScience #MachineLearning #MonitoringAndEvaluation #DigitalHealth
