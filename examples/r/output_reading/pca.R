source("_common.R")
d <- latent_teaching()
fit <- prcomp(d,scale.=TRUE); print(summary(fit)); print(fit$rotation)
prop <- fit$sdev^2/sum(fit$sdev^2)
finish(c(first_prop=prop[1],three_prop=sum(prop[1:3]),first_eigenvalue=fit$sdev[1]^2),list(variance=data.frame(component=1:9,eigenvalue=fit$sdev^2,proportion=prop,cumulative=cumsum(prop)),loadings=data.frame(item=rownames(fit$rotation),fit$rotation)))

