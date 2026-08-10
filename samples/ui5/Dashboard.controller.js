sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/m/MessageToast",
  "sap/ui/model/json/JSONModel"
], function (Controller, MessageToast, JSONModel) {
  "use strict";

  return Controller.extend("z.cvi.auto.controller.Dashboard", {

    onInit: function () {
      const oModel = new JSONModel({
        systemType: "ECC",
        systemTier: "DEV",
        notes: [],
        prompt: "",
        streamLog: "",
        result: null
      });
      this.getView().setModel(oModel, "vm");
    },

    // ----------------------------------------------------------------
    // Triggered by the "Analyze & Implement SAP Notes" button on the
    // Fiori-freestyle dashboard delivered by the BTP AI Agent.
    // ----------------------------------------------------------------
    onAnalyzeImplement: function () {
      const vm = this.getView().getModel("vm");
      const body = {
        system_type: vm.getProperty("/systemType"),
        system_tier: vm.getProperty("/systemTier"),
        notes: (vm.getProperty("/notes") || []).map(n => ({ note_number: n })),
        user_prompt: vm.getProperty("/prompt"),
        requested_by: sap.ushell?.Container?.getUser?.().getId?.() || "anonymous"
      };
      vm.setProperty("/streamLog", "");

      const url = "/notes/implement/stream?release_transports=false";
      const oCtrl = this;

      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(async resp => {
        const reader = resp.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop() || "";
          parts.forEach(part => {
            const m = part.match(/^data:\s*(.*)$/s);
            if (!m) return;
            try {
              const frame = JSON.parse(m[1]);
              oCtrl._onStreamFrame(frame);
            } catch (e) { /* ignore */ }
          });
        }
      }).catch(err => MessageToast.show("Stream failed: " + err));
    },

    _onStreamFrame: function (frame) {
      const vm = this.getView().getModel("vm");
      let log = vm.getProperty("/streamLog") || "";
      if (frame.type === "log") {
        log += `\n[${frame.level}] ${frame.step}: ${frame.message}`;
      } else if (frame.type === "start") {
        log += `\n◆ start (provider=${frame.provider})`;
      } else if (frame.type === "done") {
        vm.setProperty("/result", frame.summary);
        log += `\n✓ ${frame.summary.status} — ${frame.execution_id}`;
      }
      vm.setProperty("/streamLog", log);
    }
  });
});