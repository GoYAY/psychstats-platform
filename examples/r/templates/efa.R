d <- read.csv("your_data.csv")
items <- d[paste0("item_",1:12)] # Replace with your item columns.
stopifnot(all(vapply(items,is.numeric,logical(1))))
fit <- factanal(na.omit(items),factors=3,rotation="varimax")
print(fit$loadings,cutoff=.30); fit$uniquenesses
# Decide factor count using theory and parallel analysis, not eigenvalues alone.
