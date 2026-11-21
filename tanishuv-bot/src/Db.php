<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

use PDO;
use PDOStatement;

final class Db
{
    public PDO $pdo;
    private string $lockPrefix;

    public function __construct(array $c)
    {
        $dsn = sprintf(
            'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
            $c['host'] ?? 'localhost',
            (int)($c['port'] ?? 3306),
            $c['name'] ?? ''
        );
        try {
            $this->pdo = new PDO($dsn, (string)($c['user'] ?? ''), (string)($c['pass'] ?? ''), [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
                PDO::ATTR_STRINGIFY_FETCHES => false,
            ]);
        } catch (\PDOException $e) {
            // Xabar matnida parol bo‘lmaydi, lekin baribir faqat kodni qaytaramiz.
            throw new \RuntimeException('MySQL ulanish xatosi (kod ' . $e->getCode() . ')');
        }
        $this->pdo->exec("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci");
        $this->pdo->exec("SET time_zone = '+00:00'");
        $this->pdo->exec("SET SESSION innodb_lock_wait_timeout = 15");
        // Lock nomi shu bazaga bog‘langan: boshqa loyiha bilan to‘qnashmaydi (max 64 belgi).
        $this->lockPrefix = self::lockPrefixFor((string)($c['name'] ?? ''));
    }

    public function q(string $sql, array $p = []): PDOStatement
    {
        $st = $this->pdo->prepare($sql);
        $st->execute(array_values($p));
        return $st;
    }

    public function one(string $sql, array $p = []): ?array
    {
        $r = $this->q($sql, $p)->fetch();
        return $r === false ? null : $r;
    }

    public function all(string $sql, array $p = []): array
    {
        return $this->q($sql, $p)->fetchAll();
    }

    public function val(string $sql, array $p = []): mixed
    {
        $r = $this->q($sql, $p)->fetchColumn();
        return $r === false ? null : $r;
    }

    public function exec(string $sql, array $p = []): int
    {
        return $this->q($sql, $p)->rowCount();
    }

    public function lastId(): int
    {
        return (int)$this->pdo->lastInsertId();
    }

    public function begin(): void
    {
        $this->pdo->beginTransaction();
    }

    public function commit(): void
    {
        $this->pdo->commit();
    }

    public function rollBack(): void
    {
        if ($this->pdo->inTransaction()) {
            $this->pdo->rollBack();
        }
    }

    public function inTx(): bool
    {
        return $this->pdo->inTransaction();
    }

    public static function isRetryable(\Throwable $e): bool
    {
        if (!$e instanceof \PDOException) {
            return false;
        }
        $code = (int)($e->errorInfo[1] ?? 0);
        return $code === 1213 || $code === 1205;
    }

    public static function isDuplicate(\Throwable $e): bool
    {
        return $e instanceof \PDOException && (int)($e->errorInfo[1] ?? 0) === 1062;
    }

    /** Tranzaksiya; deadlock bo‘lsa 3 martagacha qayta urinadi. */
    public function tx(callable $fn): mixed
    {
        for ($i = 0; ; $i++) {
            $this->begin();
            try {
                $r = $fn($this);
                $this->commit();
                return $r;
            } catch (\Throwable $e) {
                $this->rollBack();
                if ($i < 3 && self::isRetryable($e)) {
                    usleep(20000 * ($i + 1));
                    continue;
                }
                throw $e;
            }
        }
    }

    public static function lockPrefixFor(string $dbName): string
    {
        return 'tb' . substr(hash('sha256', $dbName), 0, 12) . ':';
    }

    public function lockName(string $name): string
    {
        return substr($this->lockPrefix . $name, 0, 64);
    }

    public function getLock(string $name, int $timeout = 0): bool
    {
        return (int)$this->val('SELECT GET_LOCK(?, ?)', [$this->lockName($name), $timeout]) === 1;
    }

    public function releaseLock(string $name): void
    {
        $this->val('SELECT RELEASE_LOCK(?)', [$this->lockName($name)]);
    }

    public function setting(string $name, ?string $default = null): ?string
    {
        $v = $this->val('SELECT value FROM tb_settings WHERE name = ?', [$name]);
        return $v === null ? $default : (string)$v;
    }

    public function setSetting(string $name, string $value): void
    {
        $this->exec(
            'INSERT INTO tb_settings (name, value, updated_at) VALUES (?, ?, UTC_TIMESTAMP())
             ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)',
            [$name, $value]
        );
    }

    public function deleteSetting(string $name): void
    {
        $this->exec('DELETE FROM tb_settings WHERE name = ?', [$name]);
    }
}
