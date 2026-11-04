source("_common.R")
d <- read.csv("scale_items.csv"); items <- paste0("item_",1:12)
model <- 'f1 =~ item_1+item_2+item_3+item_4
f2 =~ item_5+item_6+item_7+item_8
f3 =~ item_9+item_10+item_11+item_12'
fit <- lavaan::cfa(model,d,ordered=items,estimator="WLSMV")
check_sem(fit); print(summary(fit,fit.measures=TRUE,standardized=TRUE))
m <- lavaan::fitMeasures(fit)
finish(c(chi_squared=unname(m["chisq.scaled"]),df=unname(m["df.scaled"]),p=unname(m["pvalue.scaled"]),cfi=unname(m["cfi.scaled"]),rmsea=unname(m["rmsea.scaled"]),srmr=unname(m["srmr"])),sem_tables(fit))
