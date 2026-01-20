 An agent that runs on each {{< glossary_tooltip text="node" term_id="node" >}} in the cluster. It makes sure that {{< glossary_tooltip text="containers" term_id="container" >}} are running in a {{< glossary_tooltip text="Pod" term_id="pod" >}}.

<!--more-->


The [kubelet](/docs/reference/command-line-tools-reference/kubelet/) takes a set of PodSpecs that 
are provided through various mechanisms and ensures that the containers described in those 
PodSpecs are running and healthy. The kubelet doesn't manage containers which were not created by 
Kubernetes.
