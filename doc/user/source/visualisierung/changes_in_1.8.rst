
Änderungen ab v1.8
==================

Ab SmartHomeNG v1.8 sind für die vollständige smartVISU Unterstützung das **websocket** Modul und
das **smartvisu** Plugins zu konfigurieren.

.. code-block:: yaml
   :caption: Ausschnitt aus **../etc/module.yaml**

   websocket:
       module_name: websocket
   #    ip: 0.0.0.0
   #    port: 2424
   #    tls_port: 2425
   #    use_tls: True
   #    tls_cert: shng.cer
   #    tls_key: shng.key
   #    sv_enabled: True
   #    sv_acl: ro
   #    sv_querydef: False


.. code-block:: yaml
   :caption: Ausschnitt aus **../etc/plugin.yaml**

   smartvisu:
       plugin_name: smartvisu
   #    smartvisu_dir: /var/www/smartvisu
   #    generate_pages: True
   #    handle_widgets: True
   #    overwrite_templates: Yes
   #    visu_style: blk


Für die vollständige Dokumentation der Parameter bitte in der Dokumentation des Websocket Moduls und des
smartVISU Plugins auf den folgenden Seiten dieser Dokumentation nachlesen:

- für das **websocket** unter :doc:`../modules/websocket/README`
- für das **smartvisu** unter :doc:`../plugins/smartvisu/README`

Falls die Funktionalitäten zur automatischen Generierung von smartVISU Seiten und zur Installation
von Widgets in die smartVISU nicht benötigt werden, ist es hinreichend das Modul **websocket**
zu konfigurieren.
