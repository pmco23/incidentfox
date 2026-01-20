 Represents one or more infrastructure resources, such as
{{< glossary_tooltip text="devices" term_id="device" >}}, that are attached to
nodes. Drivers create and manage ResourceSlices in the cluster. ResourceSlices
are used for
[dynamic resource allocation (DRA)](/docs/concepts/scheduling-eviction/dynamic-resource-allocation/).

<!--more-->

When a {{< glossary_tooltip text="ResourceClaim" term_id="resourceclaim" >}} is
created, Kubernetes uses ResourceSlices to find nodes that have access to
resources that can satisfy the claim. Kubernetes allocates resources to the
ResourceClaim and schedules the Pod onto a node that can access the resources.
