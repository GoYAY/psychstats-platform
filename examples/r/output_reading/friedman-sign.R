source("_common.R")
set.seed(4606); person <- rnorm(35); y <- cbind(A=person+rnorm(35),B=person+0.5+rnorm(35),C=person+0.7+rnorm(35))
fit <- friedman.test(y); print(fit)
difference <- y[,"B"]-y[,"A"]; nonzero <- difference[difference!=0]; sign <- binom.test(sum(nonzero>0),length(nonzero),0.5); print(sign)
finish(c(chi_squared=unname(fit$statistic),df=unname(fit$parameter),p=fit$p.value,sign_p=sign$p.value,nonzero_pairs=length(nonzero)))

