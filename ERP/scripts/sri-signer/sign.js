/** Firma SRI: factura, nota de crédito, etc. (ec-sri-invoice-signer). */
const { signInvoiceXml, signCreditNoteXml } = require("ec-sri-invoice-signer");

const SIGNERS = {
  FACTURA: signInvoiceXml,
  NOTA_CREDITO: signCreditNoteXml,
};

async function main() {
  process.stdin.setEncoding("utf8");
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
  }
  try {
    const payload = JSON.parse(input);
    const p12 = Buffer.from(payload.p12, "base64");
    const tipo = (payload.tipo || "FACTURA").toUpperCase();
    const signFn = SIGNERS[tipo] || signInvoiceXml;
    const signedXml = signFn(payload.xml, p12, {
      pkcs12Password: payload.password,
    });
    process.stdout.write(JSON.stringify({ signedXml }), "utf8");
  } catch (err) {
    process.stderr.write(String(err.message || err), "utf8");
    process.exit(1);
  }
}

main();
