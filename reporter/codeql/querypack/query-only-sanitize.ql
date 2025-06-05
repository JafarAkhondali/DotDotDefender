import javascript

module CommandLineFileNameConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {

    exists (DataFlow::PropRead pathnameResult | 
      (pathnameResult.getPropertyName() = "pathname" or pathnameResult.getPropertyName() = "url") and
      pathnameResult = source
    ) 
  }

  predicate isSink(DataFlow::Node sink) {
    exists (DataFlow::MethodCallNode includesCall |
      DataFlow::moduleMember("path", "normalize").getACall().getAnArgument() = sink or 
      ( includesCall.getMethodName() = "includes" and includesCall.getReceiver() = sink and includesCall.getArgument(0).getStringValue() = ".." )
    )
  }
}

module CommandLineFileNameFlow = TaintTracking::Global<CommandLineFileNameConfig>;

from DataFlow::Node source, DataFlow::Node sink
where CommandLineFileNameFlow::flow(source, sink)
select source, sink

