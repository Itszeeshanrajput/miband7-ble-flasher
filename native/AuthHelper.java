import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;

public class AuthHelper {
    public static byte[] hexToBytes(String s) {
        int len = s.length();
        byte[] data = new byte[len / 2];
        for (int i = 0; i < len; i += 2) {
            data[i / 2] = (byte) ((Character.digit(s.charAt(i), 16) << 4)
                                 + Character.digit(s.charAt(i+1), 16));
        }
        return data;
    }

    public static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    public static byte[] aesEncrypt(byte[] data, byte[] key) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/ECB/NoPadding");
        SecretKeySpec keySpec = new SecretKeySpec(key, "AES");
        cipher.init(Cipher.ENCRYPT_MODE, keySpec);
        return cipher.doFinal(data);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("Usage: java AuthHelper <genpub|compute> ...");
            System.exit(1);
        }

        if (args[0].equals("genpub")) {
            byte[] prv = hexToBytes(args[1]);
            byte[] pub = ECDH_B163.ecdh_generate_public(prv);
            System.out.println(bytesToHex(pub));
        } else if (args[0].equals("compute")) {
            byte[] prv = hexToBytes(args[1]);
            byte[] remotePub = hexToBytes(args[2]);
            byte[] remoteRand = hexToBytes(args[3]);
            byte[] authKey = hexToBytes(args[4]);

            byte[] sharedEC = ECDH_B163.ecdh_generate_shared(prv, remotePub);
            if (sharedEC == null) {
                System.err.println("Shared secret generation failed!");
                System.exit(1);
            }

            byte[] finalSessionKey = new byte[16];
            for (int i = 0; i < 16; i++) {
                finalSessionKey[i] = (byte) (sharedEC[i + 8] ^ authKey[i]);
            }

            byte[] enc1 = aesEncrypt(remoteRand, authKey);
            byte[] enc2 = aesEncrypt(remoteRand, finalSessionKey);

            byte[] cmd = new byte[33];
            cmd[0] = 0x05;
            System.arraycopy(enc1, 0, cmd, 1, 16);
            System.arraycopy(enc2, 0, cmd, 17, 16);

            System.out.println("SHARED_EC=" + bytesToHex(sharedEC));
            System.out.println("SESSION_KEY=" + bytesToHex(finalSessionKey));
            System.out.println("CMD=" + bytesToHex(cmd));
        }
    }
}
