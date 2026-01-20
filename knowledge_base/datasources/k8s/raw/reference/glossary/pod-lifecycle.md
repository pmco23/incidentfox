 The sequence of states through which a Pod passes during its lifetime.

<!--more--> 

The [Pod Lifecycle](/docs/concepts/workloads/pods/pod-lifecycle/) is defined by the states or phases of a Pod. There are five possible Pod phases: Pending, Running, Succeeded, Failed, and Unknown. A high-level description of the Pod state is summarized in the [PodStatus](/docs/reference/generated/kubernetes-api/{{< param "version" >}}/#podstatus-v1-core) `phase` field.
