source("_common.R")
set.seed(4110)
d <- data.frame(id=seq_len(180),condition=rep(c("control","practice","combined"),each=60),pre_score=rnorm(180,65,8))
d$post_score <- 20+0.75*d$pre_score+rep(c(0,4,7),each=60)+rnorm(180,0,7)
d$gain <- d$post_score-d$pre_score
fit <- lm(gain~0+condition,d)
print(summary(fit)); print(names(coef(fit)))
L <- rep(-0.5,length(coef(fit))); names(L) <- names(coef(fit)); L["conditioncontrol"] <- 1
stopifnot(length(L)==3, sum(L)==0)
estimate <- sum(L*coef(fit)); se <- sqrt(as.numeric(t(L)%*%vcov(fit)%*%L)); df <- df.residual(fit)
p <- 2*pt(-abs(estimate/se),df)
print(c(estimate=estimate,SE=se,t=estimate/se,df=df,p=p))
finish(c(difference=estimate,se=se,t=estimate/se,df=df,p=p,ci_lower=estimate-qt(0.975,df)*se,ci_upper=estimate+qt(0.975,df)*se),list(weights=data.frame(group=names(L),weight=as.numeric(L))))
