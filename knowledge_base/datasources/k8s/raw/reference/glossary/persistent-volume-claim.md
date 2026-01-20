Claims storage {{< glossary_tooltip text="resources" term_id="infrastructure-resource" >}} defined in a
{{< glossary_tooltip text="PersistentVolume" term_id="persistent-volume" >}}, so that the storage can be mounted as
a volume in a {{< glossary_tooltip text="container" term_id="container" >}}.

<!--more--> 

Specifies the amount of storage, how the storage will be accessed (read-only, read-write and/or exclusive) and how it is reclaimed (retained, recycled or deleted). Details of the storage itself are described in the PersistentVolume object.
