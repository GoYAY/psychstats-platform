source("_common.R")
set.seed(4403)
n <- 500; f1 <- rnorm(n); f2 <- rnorm(n); f3 <- 0.3*f1+0.3*f2+0.25*f1*f2+rnorm(n,sd=0.8)
factors <- list(f1,f2,f3)
d <- as.data.frame(sapply(1:9,function(j)0.8*factors[[ceiling(j/3)]]+rnorm(n,sd=0.6))); names(d) <- paste0("x",1:9)
products <- semTools::indProd(d,var1=c("x1","x2","x3"),var2=c("x4","x5","x6"),match=TRUE,meanC=TRUE,doubleMC=TRUE,namesProd=c("p1","p2","p3"))
model <- paste(measurement_model,'interaction =~ p1+p2+p3
f3 ~ b1*f1+b2*f2+bw*interaction',sep="\n")
fit <- lavaan::sem(model,products,estimator="MLR",meanstructure=TRUE)
check_sem(fit); print(summary(fit,fit.measures=TRUE,standardized=TRUE))
pe <- lavaan::parameterEstimates(fit); b1 <- pe$est[pe$label=="b1"]; bw <- pe$est[pe$label=="bw"]
v <- lavaan::lavInspect(fit,"vcov"); values <- c(-1,0,1); slopes <- b1+bw*values
ses <- sapply(values,function(w)sqrt(v["b1","b1"]+w*w*v["bw","bw"]+2*w*v["b1","bw"]))
tab <- data.frame(f2_marker_units=values,slope=slopes,se=ses,ci_lower=slopes-qnorm(0.975)*ses,ci_upper=slopes+qnorm(0.975)*ses)
print(tab)
finish(c(interaction=bw,p=pe$pvalue[pe$label=="bw"],mean_slope=b1),list(parameters=pe,simple_slopes=tab))
