// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from "vscode";
import {
  LanguageClient,
  ServerOptions,
  LanguageClientOptions,
} from "vscode-languageclient/node";

let client: LanguageClient;

// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {
  // If the extension is launched in debug mode then the debug server options are used
  // Otherwise the run options are used
  const serverOptions: ServerOptions = {
    command: "confit-lsp",
  };

  // Options to control the language client
  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "toml" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.toml"),
    },
  };
  // Create the language client and start the client.
  client = new LanguageClient(
    "confit-lsp",
    "LSP for Confit",
    serverOptions,
    clientOptions,
  );

  // Start the client. This will also launch the server
  client.start();
}

// This method is called when your extension is deactivated
export function deactivate() {}
