// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  ServerOptions,
  LanguageClientOptions,
} from "vscode-languageclient/node";

async function getPythonPath(): Promise<string | undefined> {
  const pythonExtension = vscode.extensions.getExtension("ms-python.python");

  if (!pythonExtension) {
    vscode.window.showErrorMessage("Python extension is not installed");
    return undefined;
  }

  if (!pythonExtension.isActive) {
    await pythonExtension.activate();
  }

  const pythonApi = pythonExtension.exports;
  const activeInterpreter =
    await pythonApi.environments.getActiveEnvironmentPath();

  return activeInterpreter.path;
}

let client: LanguageClient;

// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export async function activate(context: vscode.ExtensionContext) {
  let python = await getPythonPath();
  let command: string;

  if (python) {
    command = path.join(python, "..", "confit-lsp");
  } else {
    command = path.join(".venv", "bin", "confit-lsp");
  }

  // If the extension is launched in debug mode then the debug server options are used
  // Otherwise the run options are used
  const serverOptions: ServerOptions = {
    command: command,
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
export function deactivate(): Thenable<void> | undefined {
  if (!client) {
    return undefined;
  }
  return client.stop();
}
