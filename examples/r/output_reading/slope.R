source("_common.R")
d <- read.csv("nested_classrooms.csv"); d$class_id <- factor(d$class_id)
d$motivation_mean <- ave(d$motivation,d$class_id,FUN=mean); d$mw <- d$motivation-d$motivation_mean
d$tc <- d$teacher_support-mean(d$teacher_support)
fit <- nlme::lme(achievement~mw*tc+motivation_mean,d,random=list(class_id=nlme::pdDiag(~mw)),method="REML",control=nlme::lmeControl(msMaxIter=200))
print(summary(fit)); print(nlme::VarCorr(fit))
tab <- summary(fit)$tTable; variance <- nlme::VarCorr(fit)
finish(c(interaction=tab["mw:tc","Value"],p=tab["mw:tc","p-value"],slope_variance=as.numeric(variance["mw","Variance"]),groups=nlevels(d$class_id)),list(fixed=data.frame(term=rownames(tab),tab),random=data.frame(term=rownames(variance),variance=as.numeric(variance[,"Variance"]))))

