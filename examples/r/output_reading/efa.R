source("_common.R")
set.seed(4302)
d <- read.csv("scale_items.csv"); items <- d[paste0("item_",1:12)]
poly <- psych::polychoric(items)$rho
kmo <- psych::KMO(poly); bartlett <- psych::cortest.bartlett(poly,n=nrow(items))
print(kmo); print(bartlett)
parallel <- psych::fa.parallel(poly,n.obs=nrow(items),fa="fa",n.iter=20,plot=FALSE); print(parallel$nfact)
fit <- psych::fa(poly,nfactors=3,n.obs=nrow(items),fm="minres",rotate="oblimin"); print(fit)
stopifnot(all(fit$communality>=0),all(fit$uniquenesses>=0))
finish(c(parallel_factors=parallel$nfact,min_communality=min(fit$communality),rmsr=fit$rms,kmo=kmo$MSA,bartlett_p=bartlett$p.value),list(loadings=data.frame(item=rownames(fit$loadings),unclass(fit$loadings)),structure=data.frame(item=rownames(fit$Structure),unclass(fit$Structure)),factor_correlations=data.frame(factor=rownames(fit$Phi),fit$Phi)))
