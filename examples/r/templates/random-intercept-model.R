d <- read.csv("your_data.csv")
stopifnot(all(c("group_id","outcome","predictor") %in% names(d)))
fit <- nlme::lme(outcome ~ predictor,random=~1|group_id,data=d,method="REML")
summary(fit); nlme::VarCorr(fit)
