 Device plugins run on worker
{{< glossary_tooltip term_id="node" text="Nodes">}} and provide
{{< glossary_tooltip term_id="pod" text="Pods">}} with access to
infrastructure {{< glossary_tooltip text="resources" term_id="infrastructure-resource" >}},
such as local hardware, that require vendor-specific initialization or setup
steps.

<!--more-->

Device plugins advertise resources to the
{{< glossary_tooltip term_id="kubelet" text="kubelet" >}}, so that workload
Pods can access hardware features that relate to the Node where that Pod is running.
You can deploy a device plugin as a {{< glossary_tooltip term_id="daemonset" >}},
or install the device plugin software directly on each target Node.

See
[Device Plugins](/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
for more information.
