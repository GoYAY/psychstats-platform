source("_common.R")
d <- read.csv("cross_sectional_survey.csv")
ok <- complete.cases(d[,c("stress","well_being")]); d <- d[ok,]
a <- cor.test(d$stress,d$well_being)
b <- cor.test(d$stress,d$well_being,method="spearman",exact=FALSE)
print(a); print(b)
finish(c(r=unname(a$estimate),rho=unname(b$estimate),ci_lower=a$conf.int[1],ci_upper=a$conf.int[2],p=a$p.value,n=nrow(d)))
