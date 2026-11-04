source("_common.R")
d <- data.frame(class=rep(c("A","B","C"),each=20),condition=rep(c("training","control","control"),each=20))
units <- unique(d[c("class","condition")]); print(units)
cat("Design diagnosis: only one treated class; class and intervention are confounded. No confirmatory treatment-effect test is reported.\n")
finish(c(classes=nrow(units),records=nrow(d)),valid=FALSE)

