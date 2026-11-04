// Acha rostos nas fotos com o Vision do próprio Mac (sem IA paga, sem internet).
// Uso: rosto foto1.jpg foto2.jpg ...  →  uma linha JSON por foto:
// {"arquivo":"foto1.jpg","rostos":[{"x":0.41,"y":0.22,"w":0.18,"h":0.24}],"texto":0.03}
// x e y = canto de cima à esquerda do rosto, de 0 a 1, medido a partir do topo (como no CSS).
import Foundation
import Vision
import ImageIO

for caminho in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: caminho)
    var rostos: [[String: Double]] = []
    var texto = 0.0
    if let fonte = CGImageSourceCreateWithURL(url as CFURL, nil),
       let imagem = CGImageSourceCreateImageAtIndex(fonte, 0, nil) {
        let pedido = VNDetectFaceRectanglesRequest()
        let manipulador = VNImageRequestHandler(cgImage: imagem, options: [:])
        try? manipulador.perform([pedido])
        for r in pedido.results ?? [] {
            let b = r.boundingBox
            rostos.append(["x": Double(b.minX), "y": Double(1 - b.maxY), "w": Double(b.width), "h": Double(b.height)])
        }
        // texto na imagem (post, panfleto, banner): soma da área das linhas de texto, de 0 a 1
        let ler = VNRecognizeTextRequest()
        ler.recognitionLevel = .fast
        try? manipulador.perform([ler])
        for t in ler.results ?? [] { texto += Double(t.boundingBox.width * t.boundingBox.height) }
    }
    let saida: [String: Any] = ["arquivo": url.lastPathComponent, "rostos": rostos, "texto": min(1, texto)]
    if let dados = try? JSONSerialization.data(withJSONObject: saida), let texto = String(data: dados, encoding: .utf8) {
        print(texto)
    }
}
