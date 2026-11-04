source("_common.R")
set.seed(4203)
d <- data.frame(stress=rnorm(180,rep(c(2,5,8),each=60),1),sleep=rnorm(180,rep(c(8,7,6),each=60),0.6),wellbeing=rnorm(180,rep(c(8,6,3),each=60),1))
z <- scale(d); candidates <- lapply(2:4,function(k) kmeans(z,k,nstart=50))
tab <- data.frame(k=2:4,within_ss=sapply(candidates,function(m)m$tot.withinss),silhouette=sapply(candidates,function(m)mean(cluster::silhouette(m$cluster,dist(z))[,"sil_width"])))
best <- which.max(tab$silhouette); fit <- candidates[[best]]; stopifnot(fit$ifault==0)
print(tab); print(fit); profiles <- aggregate(d,list(cluster=fit$cluster),mean); print(profiles)
finish(c(k=tab$k[best],within_ss=fit$tot.withinss,mean_silhouette=tab$silhouette[best],min_size=min(fit$size)),list(candidates=tab,profiles=profiles))

