source("_common.R")
d <- read.csv("nested_classrooms.csv"); d$class_id <- factor(d$class_id)
null <- nlme::lme(achievement~1,d,random=~1|class_id,method="REML")
d$motivation_mean <- ave(d$motivation,d$class_id,FUN=mean)
d$motivation_within <- d$motivation-d$motivation_mean
fit <- nlme::lme(achievement~motivation_within+motivation_mean,d,random=~1|class_id,method="REML")
print(summary(null)); print(summary(fit)); print(nlme::VarCorr(null))
variance <- nlme::VarCorr(null); between <- as.numeric(variance[1,"Variance"]); within <- as.numeric(variance[2,"Variance"])
tab <- summary(fit)$tTable
finish(c(icc=between/(between+within),within_beta=tab["motivation_within","Value"],within_p=tab["motivation_within","p-value"],people=nrow(d),groups=nlevels(d$class_id)),list(fixed=data.frame(term=rownames(tab),tab)))

