source("_common.R")
d <- read.csv("cross_sectional_survey.csv"); d <- d[complete.cases(d[c("age","stress","well_being")]),]
rx <- resid(lm(stress~age,d)); ry <- resid(lm(well_being~age,d)); r <- cor(rx,ry)
df <- nrow(d)-3; statistic <- r*sqrt(df/(1-r*r)); p <- 2*pt(-abs(statistic),df)
kendall <- cor.test(d$stress,d$well_being,method="kendall",exact=FALSE)
# Binary demonstration is an observed response, not a dichotomized latent construct.
set.seed(4602); binary <- rbinom(nrow(d),1,0.4); point <- cor(binary,d$well_being); another <- rbinom(nrow(d),1,0.5); phi <- cor(binary,another)
print(c(partial_r=r,t=statistic,df=df,p=p)); print(kendall); print(c(point_biserial=point,phi=phi))
finish(c(partial_r=r,partial_p=p,kendall_tau=unname(kendall$estimate),point_biserial=point,phi=phi,df=df))

