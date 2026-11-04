d <- read.csv("your_data.csv")
stopifnot(all(c("group_id","outcome") %in% names(d)))
fit <- nlme::lme(outcome ~ 1,random=~1|group_id,data=d,method="REML")
v <- as.numeric(nlme::VarCorr(fit)[,"Variance"])[1:2]
icc <- v[1]/sum(v); icc
