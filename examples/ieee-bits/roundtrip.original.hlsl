struct Packet { uint word; float payload; };
Packet SaveWord(uint word)
{
    Packet packet;
    packet.word = asuint(word);
    packet.payload = asfloat(word);
    return packet;
}
float4 main(float4 input : COLOR0) : SV_Target
{
    Packet packet = SaveWord(asuint(input.x));
    uint restored = asuint(packet.payload);
    return float4(asfloat(restored), asfloat(packet.word), input.z, input.w);
}
