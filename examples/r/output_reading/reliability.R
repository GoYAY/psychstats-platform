source("_common.R")
d <- read.csv("scale_items.csv")
items <- d[paste0("item_",1:4)]
fit <- psych::alpha(items,check.keys=FALSE,n.iter=1)
print(fit)
finish(c(alpha=fit$total$raw_alpha,standardized_alpha=fit$total$std.alpha,average_r=fit$total$average_r,min_item_rest=min(fit$item.stats$r.drop),n=nrow(items)),list(items=data.frame(item=rownames(fit$item.stats),fit$item.stats)))

