source("_common.R")
observed <- c(review=48,retrieval=75,combined=57)
reference <- c(review=0.25,retrieval=0.50,combined=0.25)
fit <- chisq.test(observed,p=reference)
print(fit)
table <- data.frame(strategy=names(observed),observed=as.numeric(observed),
 expected=as.numeric(fit$expected),pearson_residual=as.numeric(fit$residuals))
print(table)
finish(c(N=sum(observed),chi_square=unname(fit$statistic),df=unname(fit$parameter),
 p=fit$p.value,w=sqrt(unname(fit$statistic)/sum(observed))),list(observed_expected=table))
