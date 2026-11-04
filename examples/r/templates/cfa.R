# CFA requires an explicit measurement model. Install lavaan separately if available.
d <- read.csv("your_data.csv")
stopifnot(all(paste0("item_",1:12) %in% names(d)))
if (!requireNamespace("lavaan",quietly=TRUE)) stop("Install lavaan to run this template")
model <- 'F1 =~ item_1 + item_2 + item_3 + item_4
F2 =~ item_5 + item_6 + item_7 + item_8
F3 =~ item_9 + item_10 + item_11 + item_12'
fit <- lavaan::cfa(model,data=d)
lavaan::summary(fit,fit.measures=TRUE,standardized=TRUE)
